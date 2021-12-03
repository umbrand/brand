# Replay Test
This graph replays data from an RDB file and uses it to test the decoding pipeline.

## Notes
- `20211112T1546_pop` (real monkey, direct control)
- `20211112T1630_pop` (real monkey, brain control attempt 1)
    - The `decoder` stream does not contain any entries, so disregard this file.
- `20211112T1646_pop` (real monkey, brain control attempt 2)
    - Decoder predictions are stuck at (922, -32767)
- `20211112_Pop_Model.pkl` -> trained decoder based on `20211112T1546_pop`

| stream                    | `20211112T1546_pop` | `20211112T1630_pop` | `20211112T1646_pop` |
| ------------------------- | ------------------- | ------------------- | ------------------- |
| behaviorControl           |          X          |          X          |          X          |
| continuousNeural          |          X          |          X          |          X          |
| cursorData                |          X          |          X          |          X          |
| decoder                   |                     |          X          |          X          |
| filteredCerebusAdapter    |          X          |          X          |          X          |
| rawEMG                    |                     |          X          |          X          |
| state                     |          X          |          X          |          X          |
| targetData                |          X          |          X          |          X          |
| taskInput                 |          X          |          X          |          X          |
| thresholdCrossings        |          X          |          X          |          X          |
| thresholdValues           |          X          |          X          |          X          |