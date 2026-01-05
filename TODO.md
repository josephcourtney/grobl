- [ ] Make `detect_text` a true probe: only read `probe_size`, classify, and return `is_text` without `content`. Do not read the remainder.
- [ ] Check `excluded_from_print` before reading contents:
   * If excluded from print, you can often avoid full content reads entirely (depending on whether you still want line counts).
- [ ] Guard against “binary but UTF-8 decodable”: your current NUL-byte heuristic + UTF-8 decode will misclassify some binaries and then read them fully; a stricter heuristic (e.g., ratio of non-text bytes in the probe) prevents pathological reads.

