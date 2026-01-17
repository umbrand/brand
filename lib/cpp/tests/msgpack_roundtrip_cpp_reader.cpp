#include "brand/node.hpp"

#include <boost/variant/get.hpp>
#include <cstdint>
#include <iostream>
#include <map>
#include <string>
#include <vector>

namespace {

using Variant = msgpack::type::variant;
using VariantMap = std::map<Variant, Variant>;
using VariantVec = std::vector<Variant>;
using VariantMultiMap = std::multimap<Variant, Variant>;

void print_indent(std::ostream &out, int indent) {
  for (int i = 0; i < indent; ++i) {
    out << ' ';
  }
}

void print_variant(std::ostream &out, const Variant &v, int indent, int depth);

void print_map(std::ostream &out, const VariantMap &map, int indent,
               int depth) {
  out << "{";
  if (!map.empty()) {
    out << "\n";
  }
  for (auto it = map.begin(); it != map.end(); ++it) {
    print_indent(out, indent + 2);
    print_variant(out, it->first, indent + 2, depth + 1);
    out << ": ";
    print_variant(out, it->second, indent + 2, depth + 1);
    if (std::next(it) != map.end()) {
      out << ",";
    }
    out << "\n";
  }
  print_indent(out, indent);
  out << "}";
}

void print_multimap(std::ostream &out, const VariantMultiMap &map, int indent,
                    int depth) {
  out << "{";
  if (!map.empty()) {
    out << "\n";
  }
  for (auto it = map.begin(); it != map.end(); ++it) {
    print_indent(out, indent + 2);
    print_variant(out, it->first, indent + 2, depth + 1);
    out << ": ";
    print_variant(out, it->second, indent + 2, depth + 1);
    if (std::next(it) != map.end()) {
      out << ",";
    }
    out << "\n";
  }
  print_indent(out, indent);
  out << "}";
}

void print_variant(std::ostream &out, const Variant &v, int indent,
                   int depth) {
  if (depth > 4) {
    out << "...";
    return;
  }
  if (const auto *p = boost::get<msgpack::type::nil_t>(&v)) {
    (void)p;
    out << "null";
  } else if (const auto *p = boost::get<bool>(&v)) {
    out << (*p ? "true" : "false");
  } else if (const auto *p = boost::get<int64_t>(&v)) {
    out << *p;
  } else if (const auto *p = boost::get<uint64_t>(&v)) {
    out << *p;
  } else if (const auto *p = boost::get<double>(&v)) {
    out << *p;
  } else if (const auto *p = boost::get<std::string>(&v)) {
    out << '"' << *p << '"';
  } else if (const auto *p = boost::get<VariantVec>(&v)) {
    out << "[";
    for (size_t i = 0; i < p->size(); ++i) {
      print_variant(out, (*p)[i], indent + 2, depth + 1);
      if (i + 1 < p->size()) {
        out << ", ";
      }
    }
    out << "]";
  } else if (const auto *p = boost::get<VariantMap>(&v)) {
    print_map(out, *p, indent, depth);
  } else if (const auto *p = boost::get<VariantMultiMap>(&v)) {
    print_multimap(out, *p, indent, depth);
  } else {
    out << "<unsupported>";
  }
}

bool get_map_value(const VariantMap &map, const std::string &key,
                   Variant *out) {
  auto it = map.find(Variant(key));
  if (it == map.end()) {
    return false;
  }
  *out = it->second;
  return true;
}

bool get_map_value(const VariantMultiMap &map, const std::string &key,
                   Variant *out) {
  auto range = map.equal_range(Variant(key));
  if (range.first == range.second) {
    return false;
  }
  *out = range.first->second;
  return true;
}

bool expect_int(const Variant &v, int64_t expected) {
  if (const auto *p = boost::get<int64_t>(&v)) {
    return *p == expected;
  }
  if (const auto *p = boost::get<uint64_t>(&v)) {
    return *p == static_cast<uint64_t>(expected);
  }
  return false;
}

bool expect_double(const Variant &v, double expected) {
  if (const auto *p = boost::get<double>(&v)) {
    return *p == expected;
  }
  return false;
}

bool expect_bool(const Variant &v, bool expected) {
  if (const auto *p = boost::get<bool>(&v)) {
    return *p == expected;
  }
  return false;
}

bool expect_string(const Variant &v, const std::string &expected) {
  if (const auto *p = boost::get<std::string>(&v)) {
    return *p == expected;
  }
  return false;
}

bool expect_list(const Variant &v, const std::vector<int64_t> &expected) {
  const auto *list = boost::get<VariantVec>(&v);
  if (!list || list->size() != expected.size()) {
    return false;
  }
  for (size_t i = 0; i < expected.size(); ++i) {
    if (!expect_int((*list)[i], expected[i])) {
      return false;
    }
  }
  return true;
}

bool expect_map(const Variant &v, int64_t a_val, int64_t b_val) {
  Variant out;
  if (const auto *map = boost::get<VariantMap>(&v)) {
    return get_map_value(*map, "a", &out) && expect_int(out, a_val) &&
           get_map_value(*map, "b", &out) && expect_int(out, b_val);
  }
  if (const auto *map = boost::get<VariantMultiMap>(&v)) {
    return get_map_value(*map, "a", &out) && expect_int(out, a_val) &&
           get_map_value(*map, "b", &out) && expect_int(out, b_val);
  }
  return false;
}

} // namespace

class MsgpackReaderNode : public brand::BRANDNode {
public:
  void work() override {}
};

int main(int argc, char *argv[]) {
  MsgpackReaderNode node;
  if (!node.initialize(argc, argv)) {
    return 1;
  }

  const std::string stream = "py_msgpack_test";
  auto entries = node.read_latest(stream, 1);
  if (entries.empty()) {
    std::cerr << "No entries found on " << stream << std::endl;
    return 1;
  }

  const auto &fields = entries[0].fields;

  auto data_it = fields.find("data");
  if (data_it == fields.end()) {
    std::cerr << "Missing data field" << std::endl;
    return 1;
  }

  Variant tmp;
  const auto *data_map = boost::get<VariantMap>(&data_it->second);
  const auto *data_multimap = boost::get<VariantMultiMap>(&data_it->second);
  if (!data_map && !data_multimap) {
    std::cerr << "Data is not a map" << std::endl;
    std::cerr << "Variant type index: " << data_it->second.which()
              << std::endl;
    return 1;
  }

  auto get_value = [&](const std::string &key, Variant *out) {
    if (data_map) {
      return get_map_value(*data_map, key, out);
    }
    return get_map_value(*data_multimap, key, out);
  };

  std::cout << "Decoded data: ";
  print_variant(std::cout, data_it->second, 0, 0);
  std::cout << std::endl;

  if (!get_value("int_val", &tmp) || !expect_int(tmp, 123)) {
    std::cerr << "int_val mismatch" << std::endl;
    return 1;
  }
  if (!get_value("float_val", &tmp) || !expect_double(tmp, 1.25)) {
    std::cerr << "float_val mismatch" << std::endl;
    return 1;
  }
  if (!get_value("str_val", &tmp) || !expect_string(tmp, "hello")) {
    std::cerr << "str_val mismatch" << std::endl;
    return 1;
  }
  if (!get_value("bool_val", &tmp) || !expect_bool(tmp, true)) {
    std::cerr << "bool_val mismatch" << std::endl;
    return 1;
  }
  if (!get_value("list_val", &tmp) || !expect_list(tmp, {1, 2, 3})) {
    std::cerr << "list_val mismatch" << std::endl;
    return 1;
  }
  if (!get_value("map_val", &tmp) || !expect_map(tmp, 1, 2)) {
    std::cerr << "map_val mismatch" << std::endl;
    return 1;
  }

  auto hdr_it = fields.find("_hdr");
  if (hdr_it == fields.end()) {
    std::cerr << "Missing _hdr field" << std::endl;
    return 1;
  }

  const auto *hdr_map = boost::get<VariantMap>(&hdr_it->second);
  const auto *hdr_multimap = boost::get<VariantMultiMap>(&hdr_it->second);
  if (!hdr_map && !hdr_multimap) {
    std::cerr << "_hdr is not a map" << std::endl;
    return 1;
  }

  auto get_hdr_value = [&](const std::string &key, Variant *out) {
    if (hdr_map) {
      return get_map_value(*hdr_map, key, out);
    }
    return get_map_value(*hdr_multimap, key, out);
  };

  std::cout << "Decoded _hdr: ";
  print_variant(std::cout, hdr_it->second, 0, 0);
  std::cout << std::endl;

  if (!get_hdr_value("parents", &tmp)) {
    std::cerr << "Missing parents in _hdr" << std::endl;
    return 1;
  }

  const auto *parents_map = boost::get<VariantMap>(&tmp);
  const auto *parents_multimap = boost::get<VariantMultiMap>(&tmp);
  if ((!parents_map && !parents_multimap) ||
      !(parents_map ? get_map_value(*parents_map, "py_parent", &tmp)
                    : get_map_value(*parents_multimap, "py_parent", &tmp)) ||
      !expect_string(tmp, "0-0")) {
    std::cerr << "parents mismatch" << std::endl;
    return 1;
  }

  std::cout << "C++ reader validation passed" << std::endl;
  return 0;
}
