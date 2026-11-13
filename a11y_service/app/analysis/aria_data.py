"""Subset of WAI-ARIA 1.2 vocabulary used by the static ARIA checks."""

VALID_ROLES = {
    "alert", "alertdialog", "application", "article", "banner", "blockquote", "button", "caption",
    "cell", "checkbox", "code", "columnheader", "combobox", "complementary", "contentinfo",
    "definition", "deletion", "dialog", "directory", "document", "emphasis", "feed", "figure",
    "form", "generic", "grid", "gridcell", "group", "heading", "img", "insertion", "link", "list",
    "listbox", "listitem", "log", "main", "marquee", "math", "menu", "menubar", "menuitem",
    "menuitemcheckbox", "menuitemradio", "meter", "navigation", "none", "note", "option",
    "paragraph", "presentation", "progressbar", "radio", "radiogroup", "region", "row",
    "rowgroup", "rowheader", "scrollbar", "search", "searchbox", "separator", "slider",
    "spinbutton", "status", "strong", "subscript", "superscript", "switch", "tab", "table",
    "tablist", "tabpanel", "term", "textbox", "time", "timer", "toolbar", "tooltip", "tree",
    "treegrid", "treeitem",
}

# attribute -> allowed token values (None = free-form / handled elsewhere)
ARIA_ATTRS: dict[str, set[str] | None] = {
    "aria-activedescendant": None, "aria-atomic": {"true", "false"},
    "aria-autocomplete": {"inline", "list", "both", "none"},
    "aria-braillelabel": None, "aria-brailleroledescription": None,
    "aria-busy": {"true", "false"}, "aria-checked": {"true", "false", "mixed"},
    "aria-colcount": None, "aria-colindex": None, "aria-colspan": None, "aria-controls": None,
    "aria-current": {"page", "step", "location", "date", "time", "true", "false"},
    "aria-describedby": None, "aria-description": None, "aria-details": None,
    "aria-disabled": {"true", "false"}, "aria-errormessage": None,
    "aria-expanded": {"true", "false"},
    "aria-flowto": None, "aria-haspopup": {"true", "false", "menu", "listbox", "tree", "grid", "dialog"},
    "aria-hidden": {"true", "false"}, "aria-invalid": {"true", "false", "grammar", "spelling"},
    "aria-keyshortcuts": None, "aria-label": None, "aria-labelledby": None, "aria-level": None,
    "aria-live": {"off", "polite", "assertive"}, "aria-modal": {"true", "false"},
    "aria-multiline": {"true", "false"}, "aria-multiselectable": {"true", "false"},
    "aria-orientation": {"horizontal", "vertical", "undefined"}, "aria-owns": None,
    "aria-placeholder": None, "aria-posinset": None, "aria-pressed": {"true", "false", "mixed"},
    "aria-readonly": {"true", "false"}, "aria-relevant": None, "aria-required": {"true", "false"},
    "aria-roledescription": None, "aria-rowcount": None, "aria-rowindex": None,
    "aria-rowspan": None, "aria-selected": {"true", "false"}, "aria-setsize": None,
    "aria-sort": {"ascending", "descending", "none", "other"}, "aria-valuemax": None,
    "aria-valuemin": None, "aria-valuenow": None, "aria-valuetext": None,
}

IDREF_ATTRS = [
    "aria-labelledby", "aria-describedby", "aria-controls", "aria-owns",
    "aria-activedescendant", "aria-details", "aria-errormessage", "aria-flowto",
]
