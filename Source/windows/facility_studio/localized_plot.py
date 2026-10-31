"""Translate plot labels at the rendering boundary, leaving coordinates unchanged."""

from .i18n import translate


class Axes:
    def __init__(self, original):
        self.original = original

    def __getattr__(self, key):
        value = getattr(self.original, key)
        if key not in (
            "set",
            "set_title",
            "set_xlabel",
            "set_ylabel",
            "annotate",
            "text",
            "plot",
        ):
            return value

        def call(*args, **kwargs):
            args = tuple(translate(x) if isinstance(x, str) else x for x in args)
            for name in ("title", "xlabel", "ylabel", "label", "s", "text"):
                if name in kwargs:
                    kwargs[name] = translate(kwargs[name])
            return value(*args, **kwargs)

        return call


def translated_axes(original):
    return Axes(original)
