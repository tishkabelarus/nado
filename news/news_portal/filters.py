
from django_filters import FilterSet, ModelChoiceFilter
from .models import Post, Category


class PostFilter(FilterSet):
   category = ModelChoiceFilter(
       field_name = 'postcategory__category',
       queryset=Category.objects.all(),
       label='category',
       empty_label='все'
   )
   class Meta:
       model = Post
       fields = {
           'name': ['icontains'],
           'text': ['icontains'],
       }