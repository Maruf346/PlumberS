from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from jobs.models import Job, JobStatus
from .models import (
    CustomReportField,
    CustomReportResponse,
    CustomReportSubmission,
    CustomReportTemplate,
    FieldType,
)


User = get_user_model()


class CustomReportJobFlowTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com',
            password='password',
            full_name='Admin User',
            is_staff=True,
        )
        self.employee = User.objects.create_user(
            email='employee@example.com',
            password='password',
            full_name='Employee User',
        )
        self.template = CustomReportTemplate.objects.create(
            name='Site Condition Report',
            description='Dynamic report template',
        )
        self.field = CustomReportField.objects.create(
            template=self.template,
            label='Condition notes',
            field_type=FieldType.TEXTAREA,
            is_required=True,
            order=1,
        )
        self.job = Job.objects.create(
            job_name='Kitchen leak',
            status=JobStatus.IN_PROGRESS,
            assigned_to=self.employee,
        )
        self.job.custom_reports.add(self.template)

    def test_admin_job_detail_includes_custom_reports_array(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse('admin-job-detail', kwargs={'id': self.job.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('custom_reports', response.data)
        self.assertEqual(response.data['custom_reports'][0]['id'], str(self.template.id))
        self.assertEqual(response.data['custom_reports'][0]['name'], self.template.name)
        self.assertEqual(response.data['custom_reports'][0]['field_count'], 1)

    def test_employee_can_submit_attached_custom_report(self):
        self.client.force_authenticate(user=self.employee)

        response = self.client.post(
            reverse(
                'custom-report-submit',
                kwargs={'job_id': self.job.id, 'template_id': self.template.id}
            ),
            {'responses': [{'field_id': str(self.field.id), 'value': 'All clear'}]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        submission = CustomReportSubmission.objects.get(
            job=self.job,
            template=self.template,
            employee=self.employee,
        )
        self.assertTrue(
            CustomReportResponse.objects.filter(
                submission=submission,
                field=self.field,
                value='All clear',
            ).exists()
        )
