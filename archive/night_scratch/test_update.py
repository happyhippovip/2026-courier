import copy
disk_record = {"UNPROVEN": ["A", "B"]}
bundle = {"record": copy.deepcopy(disk_record)}

unproven = bundle["record"]["UNPROVEN"]
unproven.remove("A")

updates = {"UNPROVEN": unproven}

new_record = dict(disk_record)
new_record.update(updates)

print("disk_record:", disk_record)
print("new_record:", new_record)
print("Equal?", disk_record == new_record)
