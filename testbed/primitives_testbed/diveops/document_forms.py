"""Forms for document management in diveops staff portal."""

from django import forms
from django.contrib.auth import get_user_model

from django_documents.models import Document, DocumentFolder, FolderPermission, PermissionLevel

from .models import DocumentLegalHold, DocumentRetentionPolicy

User = get_user_model()


class DocumentFolderForm(forms.ModelForm):
    """Form to create or edit a document folder."""

    class Meta:
        model = DocumentFolder
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                "placeholder": "Folder name",
            }),
            "description": forms.Textarea(attrs={
                "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                "rows": 3,
                "placeholder": "Optional description",
            }),
        }


class DocumentUploadForm(forms.Form):
    """Form to upload a document to a folder."""

    file = forms.FileField(
        widget=forms.FileInput(attrs={
            "class": "block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100",
            "accept": "*/*",
        }),
    )
    document_type = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
            "placeholder": "Document type (e.g., invoice, contract)",
        }),
        help_text="Optional categorization for this document",
    )


class FolderPermissionForm(forms.Form):
    """Form to grant permission on a folder."""

    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("username"),
        widget=forms.Select(attrs={
            "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
        }),
        empty_label="Select a user...",
    )
    level = forms.ChoiceField(
        choices=PermissionLevel.choices,
        widget=forms.Select(attrs={
            "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
        }),
    )
    inherited = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={
            "class": "h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500",
        }),
        help_text="If checked, this permission applies to all subfolders",
    )


class DocumentMoveForm(forms.Form):
    """Form to move a document to a different folder."""

    destination = forms.ModelChoiceField(
        queryset=DocumentFolder.objects.all().order_by("path", "name"),
        widget=forms.Select(attrs={
            "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
        }),
        empty_label="Select destination folder...",
        help_text="Choose the folder to move this document to",
    )

    def __init__(self, *args, exclude_folder=None, **kwargs):
        """
        Initialize form, optionally excluding a folder from choices.

        Args:
            exclude_folder: Folder to exclude (e.g., current folder)
        """
        super().__init__(*args, **kwargs)
        if exclude_folder:
            self.fields["destination"].queryset = DocumentFolder.objects.exclude(
                pk=exclude_folder.pk
            ).order_by("path", "name")


class DocumentRetentionPolicyForm(forms.ModelForm):
    """Form to create or edit a document retention policy."""

    class Meta:
        model = DocumentRetentionPolicy
        fields = ["document_type", "retention_days", "trash_retention_days", "legal_basis", "description", "is_active"]
        widgets = {
            "document_type": forms.TextInput(attrs={
                "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                "placeholder": "e.g., agreement, certification, invoice",
            }),
            "retention_days": forms.NumberInput(attrs={
                "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                "placeholder": "Leave blank to keep forever",
                "min": "0",
            }),
            "trash_retention_days": forms.NumberInput(attrs={
                "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                "min": "1",
            }),
            "legal_basis": forms.TextInput(attrs={
                "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                "placeholder": "e.g., IRS 7-year rule, PADI records requirement",
            }),
            "description": forms.Textarea(attrs={
                "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                "rows": 3,
                "placeholder": "Explain why this retention period is required",
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500",
            }),
        }
        help_texts = {
            "retention_days": "Days to keep documents of this type after creation. Leave blank to keep forever.",
            "trash_retention_days": "Days to keep in Trash before automatic permanent deletion (default: 30).",
            "is_active": "Uncheck to disable this policy without deleting it.",
        }


class DocumentLegalHoldForm(forms.Form):
    """Form to place a legal hold on a document."""

    reason = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
            "placeholder": "e.g., Litigation: Smith v. DiveShop",
        }),
        help_text="Reason for placing the hold",
    )
    reference = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
            "placeholder": "e.g., Case #12345",
        }),
        help_text="Case number, ticket number, or other reference",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
            "rows": 3,
            "placeholder": "Additional details about this hold",
        }),
    )


class DocumentLegalHoldReleaseForm(forms.Form):
    """Form to release a legal hold on a document."""

    release_reason = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            "class": "block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
            "placeholder": "e.g., Case dismissed, Litigation concluded",
        }),
        help_text="Reason for releasing the hold",
    )
