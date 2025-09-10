from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from django.urls import reverse
from django.core.cache import cache
import re


class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    subscribers = models.ManyToManyField(User, related_name='subscribed_categories', blank=True)

    def __str__(self):
        return f'{self.name}'

class Author(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    rating=models.IntegerField(default=0)
    def __str__(self):
        return f'{self.user.username}'
    
    def update_rating(self):
        article_rating = self.post_set.aggregate(
        total_article_rating=Sum('rating') * 3
        )['total_article_rating'] or 0
    
        # Суммарный рейтинг комментариев автора
        author_comments_rating = self.user.comment_set.aggregate(
        total_comment_rating=Sum('rating')
        )['total_comment_rating'] or 0
    
        # Суммарный рейтинг комментариев к статьям автора
        article_comments_rating = Comment.objects.filter(
        comment_post__author=self  # Изменено с post__author на comment_post__author
        ).aggregate(
        total_article_comments_rating=Sum('rating')
        )['total_article_comments_rating'] or 0
    
        self.rating = (
        article_rating + 
        author_comments_rating + 
        article_comments_rating
        )
        self.save()
        

class Post(models.Model):
    ARTICLE = 'AR'
    NEWS = 'NW'
    POST_TYPES = [
        (ARTICLE, 'Статья'),
        (NEWS, 'Новость'),
    ]

    article_or_news = models.CharField(max_length=2, choices=POST_TYPES)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)  
    creation_time=models.DateTimeField(auto_now_add=True)
    category = models.ManyToManyField(Category, through = 'PostCategory')
    name=models.CharField(max_length=255)
    text=models.TextField()
    rating=models.IntegerField(default=0)

    def __str__(self):
        return f'{self.name} | {self.author}'

    def get_absolute_url(self):
        return reverse('post_detail', args=[str(self.id)])

    def like(self):
        self.rating += 1
        self.save()

    def dislike(self):
        self.rating -= 1
        self.save()

    def save(self, *args, **kwargs):
        # Вызываем родительский метод save
        super().save(*args, **kwargs)
        
        # Инвалидируем кэш после сохранения
        self.invalidate_cache()
    
    def delete(self, *args, **kwargs):
        # Инвалидируем кэш перед удалением
        self.invalidate_cache()
        super().delete(*args, **kwargs)
    
    def invalidate_cache(self):
        """Инвалидирует кэш, связанный с этой статьей"""
        # Вспомогательная функция для удаления по шаблону
        def delete_pattern(pattern):
            try:
                if hasattr(cache, '_cache') and hasattr(cache._cache, 'keys'):
                    cache_keys = list(cache._cache.keys())
                    pattern_regex = re.compile(pattern.replace('*', '.*'))
                    for key in cache_keys:
                        if isinstance(key, str) and pattern_regex.search(key):
                            cache.delete(key)
            except (AttributeError, TypeError):
                pass
        
        delete_pattern(f'post_detail_{self.id}_*')
        delete_pattern('posts_list_*')
        delete_pattern('post_search_*')
        delete_pattern('posts_count_*')
        delete_pattern(f'related_posts_{self.id}')
        delete_pattern('home_page')

class PostCategory(models.Model):
    post=models.ForeignKey(Post, on_delete=models.CASCADE)
    category=models.ForeignKey(Category, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('post', 'category')

    def __str__(self):
        return f'{self.category} | {self.post}'



class Comment(models.Model):
    comment_post=models.ForeignKey(Post, on_delete=models.CASCADE)
    comment_user=models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    date_upload=models.DateTimeField(auto_now_add=True)
    rating=models.IntegerField(default=0)

    def like(self):
        self.rating += 1
        self.save()

    def dislike(self):
        self.rating -= 1
        self.save()

    def __str__(self):
        return f'{self.comment_post} | {self.text}'