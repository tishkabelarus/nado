from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from datetime import datetime, timedelta
from .models import Category, Post

def send_weekly_digest():
    week_ago = datetime.now() - timedelta(days=7)
    
    for category in Category.objects.prefetch_related('subscribers'):
        new_posts = Post.objects.filter(
            category=category,
            creation_time__gte=week_ago,
            article_or_news='AR'
        ).order_by('-creation_time')
        
        if not new_posts:
            continue
            
        for user in category.subscribers.all():
            if not user.email:
                continue
                
            subject = f'Еженедельная подборка в разделе "{category.name}"'
            
            html_content = render_to_string('email/weekly_digest.html', {
                'user': user,
                'category': category,
                'posts': new_posts,
            })
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=html_content,
                from_email=None,
                to=[user.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()