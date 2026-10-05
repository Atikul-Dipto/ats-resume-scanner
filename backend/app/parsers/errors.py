class DocumentTooLarge(ValueError):
    """The upload is a valid document but exceeds a processing limit."""


class UnsupportedDocument(ValueError):
    """The upload isn't a PDF/DOCX, or its contents don't match its extension."""
