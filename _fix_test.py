content = open("tests/unit/events/test_event_system.py", encoding="utf-8").read()
cutoff = content.find("\n\nTests cover:")
if cutoff == -1:
    print("marker not found, length:", len(content))
else:
    new_content = content[:cutoff] + "\n"
    open("tests/unit/events/test_event_system.py", "w", encoding="utf-8").write(
        new_content
    )
    print("done, chars:", len(new_content))
