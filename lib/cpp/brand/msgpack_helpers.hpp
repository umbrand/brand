// Helper utilities for msgpack payloads in C++ Brand nodes.
// These wrappers hide msgpack::type::variant map/multimap details and provide
// typed setters/getters similar to Python dict usage.
#ifndef BRAND_MSGPACK_HELPERS_HPP
#define BRAND_MSGPACK_HELPERS_HPP

#include <cstdint>
#include <map>
#include <string>
#include <vector>

#include <boost/variant/get.hpp>
#include <msgpack/type.hpp>

namespace brand {

using MsgpackVariant = msgpack::type::variant;
using MsgpackVariantMap = std::map<MsgpackVariant, MsgpackVariant>;
using MsgpackVariantMultiMap = std::multimap<MsgpackVariant, MsgpackVariant>;
using MsgpackVariantVec = std::vector<MsgpackVariant>;

class MsgpackBuilder {
public:
  void set(const std::string &key, int64_t value) {
    data_[key] = value;
  }

  void set(const std::string &key, uint64_t value) {
    data_[key] = value;
  }

  void set(const std::string &key, double value) {
    data_[key] = value;
  }

  void set(const std::string &key, bool value) {
    data_[key] = value;
  }

  void set(const std::string &key, const std::string &value) {
    data_[key] = value;
  }

  void set(const std::string &key, const char *value) {
    data_[key] = std::string(value);
  }

  void set_list(const std::string &key, const std::vector<int64_t> &values) {
    MsgpackVariantVec list;
    list.reserve(values.size());
    for (int64_t v : values) {
      list.push_back(v);
    }
    data_[key] = list;
  }

  void set_list(const std::string &key, const std::vector<double> &values) {
    MsgpackVariantVec list;
    list.reserve(values.size());
    for (double v : values) {
      list.push_back(v);
    }
    data_[key] = list;
  }

  void set_list(const std::string &key,
                const std::vector<std::string> &values) {
    MsgpackVariantVec list;
    list.reserve(values.size());
    for (const auto &v : values) {
      list.push_back(v);
    }
    data_[key] = list;
  }

  void set_map(const std::string &key,
               const std::map<std::string, std::string> &values) {
    MsgpackVariantMap map_values;
    for (const auto &pair : values) {
      map_values[MsgpackVariant(pair.first)] = MsgpackVariant(pair.second);
    }
    data_[key] = map_values;
  }

  const std::map<std::string, MsgpackVariant> &data() const {
    return data_;
  }

private:
  std::map<std::string, MsgpackVariant> data_;
};

class MsgpackView {
public:
  explicit MsgpackView(const MsgpackVariant &value)
      : value_(&value),
        map_(boost::get<MsgpackVariantMap>(&value)),
        multimap_(boost::get<MsgpackVariantMultiMap>(&value)) {}

  bool is_map() const { return map_ || multimap_; }

  bool get(const std::string &key, MsgpackVariant *out) const {
    if (map_) {
      auto it = map_->find(MsgpackVariant(key));
      if (it == map_->end()) {
        return false;
      }
      *out = it->second;
      return true;
    }
    if (multimap_) {
      auto range = multimap_->equal_range(MsgpackVariant(key));
      if (range.first == range.second) {
        return false;
      }
      *out = range.first->second;
      return true;
    }
    return false;
  }

  bool get_int64(const std::string &key, int64_t *out) const {
    MsgpackVariant v;
    if (!get(key, &v)) {
      return false;
    }
    if (const auto *p = boost::get<int64_t>(&v)) {
      *out = *p;
      return true;
    }
    if (const auto *p = boost::get<uint64_t>(&v)) {
      *out = static_cast<int64_t>(*p);
      return true;
    }
    return false;
  }

  bool get_double(const std::string &key, double *out) const {
    MsgpackVariant v;
    if (!get(key, &v)) {
      return false;
    }
    if (const auto *p = boost::get<double>(&v)) {
      *out = *p;
      return true;
    }
    if (const auto *p = boost::get<int64_t>(&v)) {
      *out = static_cast<double>(*p);
      return true;
    }
    if (const auto *p = boost::get<uint64_t>(&v)) {
      *out = static_cast<double>(*p);
      return true;
    }
    return false;
  }

  bool get_bool(const std::string &key, bool *out) const {
    MsgpackVariant v;
    if (!get(key, &v)) {
      return false;
    }
    if (const auto *p = boost::get<bool>(&v)) {
      *out = *p;
      return true;
    }
    return false;
  }

  bool get_string(const std::string &key, std::string *out) const {
    MsgpackVariant v;
    if (!get(key, &v)) {
      return false;
    }
    if (const auto *p = boost::get<std::string>(&v)) {
      *out = *p;
      return true;
    }
    return false;
  }

  bool get_list_int64(const std::string &key,
                      std::vector<int64_t> *out) const {
    MsgpackVariant v;
    if (!get(key, &v)) {
      return false;
    }
    const auto *list = boost::get<MsgpackVariantVec>(&v);
    if (!list) {
      return false;
    }
    out->clear();
    out->reserve(list->size());
    for (const auto &item : *list) {
      if (const auto *p = boost::get<int64_t>(&item)) {
        out->push_back(*p);
      } else if (const auto *p = boost::get<uint64_t>(&item)) {
        out->push_back(static_cast<int64_t>(*p));
      } else {
        return false;
      }
    }
    return true;
  }

  bool get_list_double(const std::string &key,
                       std::vector<double> *out) const {
    MsgpackVariant v;
    if (!get(key, &v)) {
      return false;
    }
    const auto *list = boost::get<MsgpackVariantVec>(&v);
    if (!list) {
      return false;
    }
    out->clear();
    out->reserve(list->size());
    for (const auto &item : *list) {
      if (const auto *p = boost::get<double>(&item)) {
        out->push_back(*p);
      } else if (const auto *p = boost::get<int64_t>(&item)) {
        out->push_back(static_cast<double>(*p));
      } else if (const auto *p = boost::get<uint64_t>(&item)) {
        out->push_back(static_cast<double>(*p));
      } else {
        return false;
      }
    }
    return true;
  }

  bool get_map(const std::string &key, MsgpackView *out) const {
    MsgpackVariant v;
    if (!get(key, &v)) {
      return false;
    }
    MsgpackView view(v);
    if (!view.is_map()) {
      return false;
    }
    *out = view;
    return true;
  }

private:
  const MsgpackVariant *value_;
  const MsgpackVariantMap *map_;
  const MsgpackVariantMultiMap *multimap_;
};

} // namespace brand

#endif // BRAND_MSGPACK_HELPERS_HPP
