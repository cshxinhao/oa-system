from django.views.generic import ListView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django import forms
from .models import Document

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'file', 'description', 'is_public']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = 'docs/doc_list.html'
    context_object_name = 'documents'

    def get_queryset(self):
        # 所有人可见的文档 + 自己上传的文档
        return Document.objects.filter(is_public=True) | Document.objects.filter(uploader=self.request.user)

class DocumentCreateView(LoginRequiredMixin, CreateView):
    model = Document
    form_class = DocumentForm
    template_name = 'docs/doc_form.html'
    success_url = reverse_lazy('docs:doc_list')

    def form_valid(self, form):
        form.instance.uploader = self.request.user
        messages.success(self.request, "文档上传成功")
        return super().form_valid(form)
