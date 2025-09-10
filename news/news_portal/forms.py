from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from allauth.account.forms import SignupForm
from django.contrib.auth.models import Group

from .models import Post, Category

class PostForm(forms.ModelForm):
   text = forms.CharField(min_length=20)
   categories = forms.ModelMultipleChoiceField(
      queryset=Category.objects.all(),
      widget=forms.CheckboxSelectMultiple,
      required=True
   )

   class Meta:
        model = Post
        fields = ['name',
                  'text',
                  'categories',
        ]

   def __init__(self, *args, **kwargs):
      self.user = kwargs.pop('user', None)
      super().__init__(*args, **kwargs)        

   def clean(self):
      cleaned_data = super().clean()
      text = cleaned_data.get("text")
      name = cleaned_data.get("name")


      if self.user:
         day_ago = timezone.now() - timezone.timedelta(hours=24)
         post_count = Post.objects.filter(
            author__user=self.user,
            creation_time__gte=day_ago,
         ).count()
            
         if post_count >= 3:
            raise ValidationError(
                    "Вы превысили лимит: не более 3 новостей в сутки!"
            )
      if name == text:
         raise ValidationError(
                "текст статьи не может быть идентичным названию."
         )
      
      return cleaned_data
   
class PostSearchForm(forms.Form):
   name = forms.CharField(
      label='Название',
      required=False,
      widget=forms.TextInput(attrs={'placeholder': 'Поиск по названию'}))
   
   author = forms.CharField(
      label='Автор',
      required=False,
      widget=forms.TextInput(attrs={'placeholder': 'Имя автора'}))
    
   date_after = forms.DateField(
      label='Дата после',
      required=False,
      widget=forms.DateInput(attrs={'type': 'date'}))
   
class CommonSignupForm(SignupForm):
    
    def save(self, request):
        user = super(CommonSignupForm, self).save(request)
        common_group = Group.objects.get(name='common')
        common_group.user_set.add(user)
        return user