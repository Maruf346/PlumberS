from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from notifications.models import Notification, NotificationType
from .models import Job, JobStatus


User = get_user_model()


class EmployeeReopenJobNotificationTests(APITestCase):
    def test_reopening_job_notifies_admins(self):
        admin = User.objects.create_user(
            email='admin@example.com',
            password='password',
            full_name='Admin User',
            is_staff=True,
        )
        employee = User.objects.create_user(
            email='employee@example.com',
            password='password',
            full_name='Employee User',
        )
        job = Job.objects.create(
            job_name='Leaking tap',
            status=JobStatus.COMPLETED,
            assigned_to=employee,
        )

        self.client.force_authenticate(user=employee)
        response = self.client.post(reverse('job-reopen', kwargs={'id': job.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification = Notification.objects.get(
            user=admin,
            notification_type=NotificationType.JOB_REOPENED,
        )
        self.assertEqual(notification.title, 'Job Reopened')
        self.assertEqual(notification.data['job_id'], str(job.id))
        self.assertEqual(notification.data['job_ref'], job.job_id)
        self.assertEqual(notification.data['actor_id'], str(employee.id))
