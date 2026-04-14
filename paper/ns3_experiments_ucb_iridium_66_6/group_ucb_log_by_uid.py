import argparse
import collections
import os
import re


def parse_event_tag(line):
    m = re.match(r"^\[UCB_DEBUG\](\[[^\]]+\])?(\[[^\]]+\])?", line)
    if not m:
        return "UNKNOWN"
    tags = []
    if m.group(1):
        tags.append(m.group(1).strip("[]"))
    if m.group(2):
        tags.append(m.group(2).strip("[]"))
    return "/".join(tags) if tags else "UNKNOWN"


def parse_fields(line):
    fields = {}
    for key, value in re.findall(r"([a-zA-Z_][a-zA-Z0-9_]*)=([^\s]+)", line):
        fields[key] = value
    return fields


def status_of(events):
    has_arrive = any(e["event"] == "ARRIVE" for e in events)
    has_drop = any(e["event"].startswith("DROP") for e in events)
    has_forward_to_dst = any(
        e["event"] == "FWD"
        and e.get("dry_run") == "0"
        and e.get("selected")
        and e.get("dst")
        and e.get("selected") == e.get("dst")
        for e in events
    )
    if has_arrive and has_drop:
        return "ARRIVE_WITH_DROP"
    if has_arrive:
        return "ARRIVE"
    if has_forward_to_dst and has_drop:
        return "FORWARDED_TO_DST_WITH_DROP"
    if has_forward_to_dst:
        return "FORWARDED_TO_DST"
    if has_drop:
        return "DROP"
    return "IN_PROGRESS"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log_file", required=True)
    parser.add_argument("--grouped_out", default="")
    parser.add_argument("--summary_out", default="")
    args = parser.parse_args()

    log_file = args.log_file
    if not os.path.isfile(log_file):
        raise FileNotFoundError(log_file)

    grouped_out = args.grouped_out if args.grouped_out else os.path.splitext(log_file)[0] + "_by_uid.txt"
    summary_out = args.summary_out if args.summary_out else os.path.splitext(log_file)[0] + "_uid_summary.txt"

    events_by_key = collections.defaultdict(list)
    skipped_lines = 0

    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            fields = parse_fields(line)
            if "uid" not in fields:
                skipped_lines += 1
                continue
            uid = fields["uid"]
            src = fields.get("src", "")
            dst = fields.get("dst", "")
            key = (uid, src, dst)
            event = parse_event_tag(line)
            events_by_key[key].append(
                {
                    "line_no": line_no,
                    "event": event,
                    "line": line,
                    "src": src,
                    "dst": dst,
                    "hop": fields.get("hop", ""),
                    "node": fields.get("node", ""),
                    "ttl": fields.get("ttl", ""),
                    "dry_run": fields.get("dry_run", ""),
                    "selected": fields.get("selected", ""),
                    "ns3_uid": fields.get("ns3_uid", "")
                }
            )

    def sort_key(item):
        uid_text = item[0][0]
        try:
            uid_num = int(uid_text)
        except ValueError:
            uid_num = 0
        return uid_num, item[0][1], item[0][2]

    sorted_items = sorted(events_by_key.items(), key=sort_key)

    with open(summary_out, "w", encoding="utf-8") as f:
        f.write("uid\tns3_uids\tsrc\tdst\tstatus\tevents\tfwd\tdrop\tarrive\tforward_to_dst\tfirst_line\tlast_line\n")
        for (uid, src, dst), events in sorted_items:
            stat = status_of(events)
            event_count = len(events)
            fwd_count = sum(1 for e in events if e["event"] == "FWD")
            drop_count = sum(1 for e in events if e["event"].startswith("DROP"))
            arrive_count = sum(1 for e in events if e["event"] == "ARRIVE")
            forward_to_dst_count = sum(
                1
                for e in events
                if e["event"] == "FWD"
                and e.get("dry_run") == "0"
                and e.get("selected")
                and e.get("dst")
                and e.get("selected") == e.get("dst")
            )
            first_line = events[0]["line_no"]
            last_line = events[-1]["line_no"]
            ns3_uids = sorted({e["ns3_uid"] for e in events if e.get("ns3_uid")})
            ns3_uids_text = ",".join(ns3_uids) if ns3_uids else "-"
            f.write(
                f"{uid}\t{ns3_uids_text}\t{src}\t{dst}\t{stat}\t{event_count}\t{fwd_count}\t{drop_count}\t{arrive_count}\t{forward_to_dst_count}\t{first_line}\t{last_line}\n"
            )

    with open(grouped_out, "w", encoding="utf-8") as f:
        for (uid, src, dst), events in sorted_items:
            stat = status_of(events)
            fwd_count = sum(1 for e in events if e["event"] == "FWD")
            drop_count = sum(1 for e in events if e["event"].startswith("DROP"))
            arrive_count = sum(1 for e in events if e["event"] == "ARRIVE")
            forward_to_dst_count = sum(
                1
                for e in events
                if e["event"] == "FWD"
                and e.get("dry_run") == "0"
                and e.get("selected")
                and e.get("dst")
                and e.get("selected") == e.get("dst")
            )
            ns3_uids = sorted({e["ns3_uid"] for e in events if e.get("ns3_uid")})
            ns3_uids_text = ",".join(ns3_uids) if ns3_uids else "-"
            f.write(
                f"=== UID {uid} ns3_uids={ns3_uids_text} src={src} dst={dst} status={stat} events={len(events)} fwd={fwd_count} drop={drop_count} arrive={arrive_count} forward_to_dst={forward_to_dst_count} ===\n"
            )
            for e in events:
                f.write(f"[line:{e['line_no']}] {e['line']}\n")
            f.write("\n")

    print(f"grouped: {grouped_out}")
    print(f"summary: {summary_out}")
    print(f"uids: {len(sorted_items)}")
    print(f"skipped_lines_without_uid: {skipped_lines}")


if __name__ == "__main__":
    main()
