# Runner bottom controls

Owner reported the report button was completely hidden in the crowded
horizontal toolbar and requested it at bottom right under the log.
Reserve a separate bottom panel before expanding packed content; support
a grid-managed base root with an appended row. Research controls occupy
two rows of four columns; report button has its own bottom-right row.
Existing callback names, disable/enable state and saved report behavior
are unchanged. The original desktop.py is not present in this release
branch; test actual Tk geometry on synthetic pack/grid base layouts
at 640x480 and 1000x600, including resize, visibility and callbacks.
Owner real full-desktop visual check remains necessary. No source access
policy, market reader, research scope or auto-update cadence change.
