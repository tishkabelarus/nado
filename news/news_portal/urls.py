from django.urls import path
from .views import PostsList, PostDetail, PostUpdate, PostDelete, PostSearchView, create_post
from django.conf import settings
from django.conf.urls.static import static
from .views import (
    NewsCreate, NewsUpdate, NewsDelete,
    ArticleCreate, ArticleUpdate, ArticleDelete, CLogoutView)
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import views as auth_views
from .views import IndexView, upgrade_me, subscribe


urlpatterns = [
    path('login/', LoginView.as_view(template_name='login_user.html'), name='login'),
    path('logout/', CLogoutView.as_view(template_name='logout_user.html'), name='logout'),
    path('', PostsList.as_view(), name='post_list'),
    path('<int:pk>', PostDetail.as_view(), name='post_detail'),
    path('create/', create_post, name='post_create'),
    path('<int:pk>/update/', PostUpdate.as_view(), name='post_update'),
    path('<int:pk>/delete/', PostDelete.as_view(), name='post_delete'),
    path('search/', PostSearchView.as_view(), name='news_search'),
    path('personal', IndexView.as_view()),
    path('upgrade/', upgrade_me, name = 'upgrade'),
    path('category/<int:category_id>/subscribe/', subscribe, name='subscribe'),


    # Новости
    path('news/create/', NewsCreate.as_view(), name='news_create'),
    path('news/<int:pk>/edit/', NewsUpdate.as_view(), name='news_edit'),
    path('news/<int:pk>/delete/', NewsDelete.as_view(), name='news_delete'),
    
    # Статьи
    path('articles/create/', ArticleCreate.as_view(), name='article_create'),
    path('articles/<int:pk>/edit/', ArticleUpdate.as_view(), name='article_edit'),
    path('articles/<int:pk>/delete/', ArticleDelete.as_view(), name='article_delete'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)