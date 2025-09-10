from django.core.management.base import BaseCommand
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util
from news_portal.tasks import send_weekly_digest
import logging

logger = logging.getLogger(__name__)

def delete_old_job_executions(max_age=604_800):
    DjangoJobExecution.objects.delete_old_job_executions(max_age)

class Command(BaseCommand):
    help = "Runs APScheduler to manage periodic tasks"

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        scheduler.add_job(
            send_weekly_digest,
            trigger=CronTrigger(day_of_week="mon", hour="8", minute="0"),
            id="weekly_digest",
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'weekly_digest' (every Monday at 8:00).")

        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(day_of_week="mon", hour="0", minute="0"),
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added weekly job: 'delete_old_job_executions'.")

        try:
            logger.info("Starting scheduler...")
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Stopping scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler shut down successfully!")