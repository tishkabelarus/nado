from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import CreateView, ListView, DetailView, UpdateView, DeleteView, TemplateView
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.core.cache import cache
from django.conf import settings
from .models import Post, Category, PostCategory, Author
from .filters import PostFilter
from .forms import PostForm
from django.urls import reverse_lazy
from .forms import PostSearchForm
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.views import LogoutView
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required
from django.db import transaction
import re
from django.utils import timezone

# Настройки кэширования
CACHE_TIMEOUT_POSTS = 300  # 5 минут для списка постов
CACHE_TIMEOUT_POST_DETAIL = 300  # 5 минут для детальной страницы
CACHE_TIMEOUT_SEARCH = 60  # 1 минута для поиска
CACHE_TIMEOUT_HOME = 60  # 1 минута для главной страницы

# Вспомогательная функция для удаления ключей по шаблону
def delete_cache_pattern(pattern):
    """
    Удаляет ключи кэша по шаблону для файлового кэша
    """
    try:
        # Получаем все ключи из кэша
        if hasattr(cache, '_cache') and hasattr(cache._cache, 'keys'):
            cache_keys = list(cache._cache.keys())
            pattern_regex = re.compile(pattern.replace('*', '.*'))
            for key in cache_keys:
                if isinstance(key, str) and pattern_regex.search(key):
                    cache.delete(key)
    except (AttributeError, TypeError):
        # Если не получается получить ключи, просто пропускаем
        pass

# Функция для получения ключа кэша статьи
def get_post_cache_key(post_id, timestamp):
    return f'post_detail_{post_id}_{timestamp}'

# Функция для получения ключа кэша списка статей
def get_posts_list_cache_key(params=''):
    return f'posts_list_{params}'

# Функция для получения ключа кэша поиска
def get_search_cache_key(params=''):
    return f'post_search_{params}'

class PostsList(ListView):
    model = Post
    ordering = '-creation_time'
    template_name = 'posts.html'
    context_object_name = 'posts'
    paginate_by = 10

    @method_decorator(cache_page(CACHE_TIMEOUT_POSTS))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        cache_key = get_posts_list_cache_key(self.request.GET.urlencode())
        queryset = cache.get(cache_key)
        
        if queryset is None:
            queryset = super().get_queryset()
            self.filterset = PostFilter(self.request.GET, queryset)
            queryset = self.filterset.qs
            cache.set(cache_key, queryset, CACHE_TIMEOUT_POSTS)
        else:
            self.filterset = PostFilter(self.request.GET, queryset)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filterset'] = self.filterset
        context['total_posts_count'] = self.filterset.qs.count()
        
        # Кэшируем количество постов
        count_cache_key = f'posts_count_{self.request.GET.urlencode()}'
        context['cached_count'] = cache.get(count_cache_key)
        if context['cached_count'] is None:
            context['cached_count'] = self.filterset.qs.count()
            cache.set(count_cache_key, context['cached_count'], CACHE_TIMEOUT_POSTS)
            
        return context


class PostDetail(DetailView): 
    model = Post
    template_name = 'post.html'
    context_object_name = 'post'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        
        # Создаем уникальный ключ на основе времени обновления статьи
        cache_key = get_post_cache_key(obj.id, obj.creation_time.timestamp())
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            # Если нет в кэше, получаем данные и кэшируем
            cached_data = {
                'object': obj,
                'cached_at': timezone.now(),
                'categories': list(obj.category.all()),
                'author_name': obj.author.user.username if obj.author else 'Неизвестный автор'
            }
            cache.set(cache_key, cached_data, CACHE_TIMEOUT_POST_DETAIL)
        
        return cached_data['object']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        
        # Получаем дополнительные данные из кэша
        cache_key = get_post_cache_key(obj.id, obj.creation_time.timestamp())
        cached_data = cache.get(cache_key)
        
        if cached_data:
            context['cached_at'] = cached_data['cached_at']
            context['categories_list'] = cached_data['categories']
            context['author_name'] = cached_data['author_name']
        
        # Кэшируем связанные статьи
        related_cache_key = f'related_posts_{obj.id}'
        related_posts = cache.get(related_cache_key)
        
        if related_posts is None:
            # Получаем статьи из тех же категорий
            categories = obj.category.all()
            if categories:
                related_posts = Post.objects.filter(
                    category__in=categories
                ).exclude(id=obj.id).distinct()[:5]
            else:
                related_posts = Post.objects.exclude(id=obj.id)[:5]
            
            cache.set(related_cache_key, related_posts, CACHE_TIMEOUT_POST_DETAIL)
        
        context['related_posts'] = related_posts
        return context


def create_post(request):
    form = PostForm()
    
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save()
            # Инвалидируем кэш после создания поста
            delete_cache_pattern(r'posts_list_.*')
            delete_cache_pattern(r'post_search_.*')
            delete_cache_pattern(r'posts_count_.*')
            delete_cache_pattern(r'related_posts_.*')
            return redirect('post_detail', pk=post.pk)

    return render(request, 'post_edit.html', {'form': form})


class PostUpdate(UpdateView):
    form_class = PostForm
    model = Post
    template_name = 'post_edit.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        # Инвалидируем кэш после обновления поста
        delete_cache_pattern(f'post_detail_{self.object.id}_.*')
        delete_cache_pattern(r'posts_list_.*')
        delete_cache_pattern(r'post_search_.*')
        delete_cache_pattern(r'posts_count_.*')
        delete_cache_pattern(r'related_posts_.*')
        return response


class PostDelete(DeleteView):
    model = Post
    template_name = 'post_delete.html'
    success_url = reverse_lazy('post_list')

    def delete(self, request, *args, **kwargs):
        # Инвалидируем кэш перед удалением
        self.object = self.get_object()
        delete_cache_pattern(f'post_detail_{self.object.id}_.*')
        delete_cache_pattern(r'posts_list_.*')
        delete_cache_pattern(r'post_search_.*')
        delete_cache_pattern(r'posts_count_.*')
        delete_cache_pattern(r'related_posts_.*')
        return super().delete(request, *args, **kwargs)


class PostSearchView(ListView):
    model = Post
    template_name = 'news_search.html'
    context_object_name = 'news'
    paginate_by = 10

    @method_decorator(cache_page(CACHE_TIMEOUT_SEARCH))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        search_params = self.request.GET.urlencode()
        cache_key = get_search_cache_key(search_params)
        
        queryset = cache.get(cache_key)
        
        if queryset is None:
            queryset = super().get_queryset()
            form = PostSearchForm(self.request.GET)
            
            if form.is_valid():
                name = form.cleaned_data.get('name')
                author = form.cleaned_data.get('author')
                date_after = form.cleaned_data.get('date_after')
                
                if name:
                    queryset = queryset.filter(name__icontains=name)
                
                if author:
                    queryset = queryset.filter(author__username__icontains=author)
                
                if date_after:
                    queryset = queryset.filter(creation_time__gte=date_after)
            
            queryset = queryset.order_by('-creation_time')
            cache.set(cache_key, queryset, CACHE_TIMEOUT_SEARCH)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = PostSearchForm(self.request.GET)
        return context


# Кэширование для создания новостей и статей
class NewsCreate(PermissionRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'new_create.html'
    permission_required = 'news_portal.add_post'

    @transaction.atomic
    def form_valid(self, form):
        author = Author.objects.get(user=self.request.user)
        
        post = form.save(commit=False)
        post.article_or_news = 'NW'
        post.author = author
        post.save()
        
        categories = form.cleaned_data['categories']
        post.category.set(categories)
        
        # Инвалидируем кэш после создания
        delete_cache_pattern(r'posts_list_.*')
        delete_cache_pattern(r'post_search_.*')
        delete_cache_pattern(r'posts_count_.*')
        delete_cache_pattern(r'related_posts_.*')
        
        return redirect(post.get_absolute_url())
    
    def get_success_url(self):
        return reverse_lazy('post_detail', kwargs={'pk': self.object.pk})


class NewsUpdate(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'new_create.html'
    permission_required = 'news_portal.change_post'
    success_url = reverse_lazy('post_list')
    
    def get_queryset(self):
        return super().get_queryset().filter(article_or_news='NW')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Инвалидируем кэш после обновления
        delete_cache_pattern(f'post_detail_{self.object.id}_.*')
        delete_cache_pattern(r'posts_list_.*')
        delete_cache_pattern(r'post_search_.*')
        delete_cache_pattern(r'posts_count_.*')
        delete_cache_pattern(r'related_posts_.*')
        return response


class NewsDelete(PermissionRequiredMixin, DeleteView):
    model = Post
    template_name = 'post_confirm_delete.html'
    permission_required = 'news_portal.delete_post'
    success_url = reverse_lazy('post_list')
    
    def get_queryset(self):
        return super().get_queryset().filter(article_or_news='NW')
    
    def delete(self, request, *args, **kwargs):
        # Инвалидируем кэш перед удалением
        self.object = self.get_object()
        delete_cache_pattern(f'post_detail_{self.object.id}_.*')
        delete_cache_pattern(r'posts_list_.*')
        delete_cache_pattern(r'post_search_.*')
        delete_cache_pattern(r'posts_count_.*')
        delete_cache_pattern(r'related_posts_.*')
        return super().delete(request, *args, **kwargs)


class ArticleCreate(PermissionRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'new_create.html'
    permission_required = 'news_portal.add_post'

    @transaction.atomic
    def form_valid(self, form):
        author = Author.objects.get(user=self.request.user)
        
        post = form.save(commit=False)
        post.article_or_news = 'AR'
        post.author = author
        post.save()
        
        categories = form.cleaned_data['categories']
        post.category.set(categories)
        
        # Инвалидируем кэш после создания
        delete_cache_pattern(r'posts_list_.*')
        delete_cache_pattern(r'post_search_.*')
        delete_cache_pattern(r'posts_count_.*')
        delete_cache_pattern(r'related_posts_.*')
        
        return redirect(post.get_absolute_url())
    
    def get_success_url(self):
        return reverse_lazy('post_detail', kwargs={'pk': self.object.pk})


class ArticleUpdate(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'article_create.html'
    permission_required = 'news_portal.change_post'
    success_url = reverse_lazy('post_list')
    
    def get_queryset(self):
        return super().get_queryset().filter(article_or_news='AR')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Инвалидируем кэш после обновления
        delete_cache_pattern(f'post_detail_{self.object.id}_.*')
        delete_cache_pattern(r'posts_list_.*')
        delete_cache_pattern(r'post_search_.*')
        delete_cache_pattern(r'posts_count_.*')
        delete_cache_pattern(r'related_posts_.*')
        return response


class ArticleDelete(PermissionRequiredMixin, DeleteView):
    model = Post
    template_name = 'post_confirm_delete.html'
    permission_required = 'news_portal.delete_post'
    success_url = reverse_lazy('post_list')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(article_or_news='AR')
    
    def delete(self, request, *args, **kwargs):
        # Инвалидируем кэш перед удалением
        self.object = self.get_object()
        delete_cache_pattern(f'post_detail_{self.object.id}_.*')
        delete_cache_pattern(r'posts_list_.*')
        delete_cache_pattern(r'post_search_.*')
        delete_cache_pattern(r'posts_count_.*')
        delete_cache_pattern(r'related_posts_.*')
        return super().delete(request, *args, **kwargs)


# Добавим кэширование для главной страницы
def home_view(request):
    cache_key = 'home_page'
    cached_data = cache.get(cache_key)
    
    if cached_data is None:
        # Получаем свежие новости и статьи
        latest_news = Post.objects.filter(
            article_or_news='NW', 
            is_published=True
        ).order_by('-creation_time')[:5]
        
        latest_articles = Post.objects.filter(
            article_or_news='AR', 
            is_published=True
        ).order_by('-creation_time')[:5]
        
        popular_posts = Post.objects.filter(
            is_published=True
        ).order_by('-rating')[:5]
        
        cached_data = {
            'latest_news': latest_news,
            'latest_articles': latest_articles,
            'popular_posts': popular_posts,
            'cached_at': timezone.now()
        }
        
        cache.set(cache_key, cached_data, CACHE_TIMEOUT_HOME)
    
    context = {
        'latest_news': cached_data['latest_news'],
        'latest_articles': cached_data['latest_articles'],
        'popular_posts': cached_data['popular_posts'],
        'cached_at': cached_data['cached_at']
    }
    
    return render(request, 'home.html', context)


# Остальные классы остаются без изменений
class CLogoutView(LogoutView):
    template_name = 'logout_user.html'
    next_page = reverse_lazy('post_list')


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = 'personal_account.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_not_author'] = not self.request.user.groups.filter(name='author').exists()
        return context


@login_required
def upgrade_me(request):
    user = request.user
    author_group = Group.objects.get(name='author')
    if not request.user.groups.filter(name='author').exists():
        author_group.user_set.add(user)
    return redirect('/posts/personal')


@login_required
def subscribe(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.user in category.subscribers.all():
        category.subscribers.remove(request.user)
    else:
        category.subscribers.add(request.user)
    return redirect('post_list')