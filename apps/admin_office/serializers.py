from rest_framework import serializers
from .models import Notice

class NoticeSerializer(serializers.ModelSerializer):
    author_name = serializers.ReadOnlyField(source='author.get_full_name')

    class Meta:
        model = Notice
        fields = ['id', 'title', 'content', 'author', 'author_name', 'published_at', 'is_published']
        read_only_fields = ['author', 'published_at']
