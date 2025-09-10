from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db import transaction
from .models import Post
import logging

logger = logging.getLogger(__name__)

def send_notifications(post):
    with transaction.atomic():
        post.refresh_from_db()
        categories = post.category.all()
        
        if not categories.exists():
            logger.warning(f"Post {post.id} действительно не имеет категорий")
            return
            
        for category in categories:
            subscribers = category.subscribers.all()
            for user in subscribers:
                try:
                    html_message = render_to_string('email_notification.html', {
                        'user': user,
                        'post': post,
                        'category': category,
                    })
                    
                    send_mail(
                        subject=f"Новая публикация: {post.name[:50]}",
                        message=strip_tags(html_message),
                        from_email=None,
                        recipient_list=[user.email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки: {str(e)}")

@receiver(m2m_changed, sender=Post.category.through)
def handle_category_change(sender, instance, action, **kwargs):
    if action == "post_add":
        transaction.on_commit(lambda: send_notifications(instance))

@receiver(post_save, sender=Post)
def handle_post_save(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(lambda: send_notifications(instance))