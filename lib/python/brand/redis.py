def xread_count(r, stream, count, startid=0, block=None) -> list:
        """
        Block and read multiple entries from a single stream

        Parameters
        ----------
        r : redis.Redis
            instance of the redis.Redis interface
        stream : bytes
            Name of the stream
        count : int
            Number of items to return
        startid : int
            The starting ID to be used for XREAD. This ID indicates the last ID
            already seen.
        block : int, optional
            Number of milliseconds to wait in each XREAD call, by default None

        Returns
        -------
        out : list
            List of entries for each stream
        """
        entry_id = startid
        n_samples = count

        # Initialize the output
        stream_entries = [None] * n_samples
        out = [[stream, stream_entries]]
        # Read from the stream
        while count > 0:
            all_streams = r.xread({stream: entry_id},
                                     count=count,
                                     block=block)
            if len(all_streams) > 0:
                stream_entries = all_streams[0][1]
                for entry in stream_entries:
                    out[0][1][n_samples - count] = entry
                    entry_id = entry[0]
                    count -= 1
        return out