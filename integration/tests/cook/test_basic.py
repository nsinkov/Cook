import json
import requests
from retrying import retry
import time
import unittest
import uuid

class CookTest(unittest.TestCase):
    _multiprocess_can_split_ = True

    @retry(stop_max_delay=120000, wait_fixed=1000)
    def wait_for_job(self, job_id, status):
        job = self.session.get('%s/rawscheduler?job=%s' % (self.cook_url, job_id))
        self.assertEqual(200, job.status_code)
        job = job.json()[0]
        self.assertEqual(status, job['status'])
        return job

    def minimal_job(self, **kwargs):
        job = {
            'max_retries': 1,
            'mem': 10,
            'cpus': 1,
            'uuid': str(uuid.uuid4()),
            'command': 'echo hello',
            'name': 'echo',
            'priority': 1
        }
        job.update(kwargs)
        return job

    def setUp(self):
        self.cook_url = 'http://localhost:12321'
        self.session = requests.Session()

    def test_basic_submit(self):
        job_spec = self.minimal_job()
        request_body = {'jobs': [ job_spec ]}
        resp = self.session.post('%s/rawscheduler' % self.cook_url, json=request_body)
        self.assertEqual(resp.status_code, 201)
        job = self.wait_for_job(job_spec['uuid'], 'completed')
        self.assertEqual('success', job['instances'][0]['status'])

    def test_failing_submit(self):
        job_spec = self.minimal_job(command='exit 1')
        resp = self.session.post('%s/rawscheduler' % self.cook_url,
                                 json={'jobs': [job_spec]})
        self.assertEqual(201, resp.status_code)
        job = self.wait_for_job(job_spec['uuid'], 'completed')
        self.assertEqual(1, len(job['instances']))
        self.assertEqual('failed', job['instances'][0]['status'])

    # def test_failing_submit_with_retries(self):
    #     job_uuid = str(uuid.uuid4())
    #     print job_uuid
    #     jobspec = self.minimal_job(job_uuid)
    #     jobspec['command'] = 'exit 1'
    #     jobspec['max_retries'] = 3
    #     resp = self.session.post('%s/rawscheduler' % self.cook_url,
    #                              json={'jobs': [jobspec]})
    #     self.assertEqual(201, resp.status_code)
    #     job = self.wait_for_job(job_uuid, 'completed')
    #     self.assertEqual(3, len(job['instances']))
    #     for instance in job['instances']:
    #         self.assertEqual('failed', instance['status'])

    def test_max_runtime_exceeded(self):
        job_spec = self.minimal_job(command='sleep 60', max_runtime=5000)
        resp = self.session.post('%s/rawscheduler' % self.cook_url,
                                 json={'jobs': [job_spec]})
        self.assertEqual(201, resp.status_code)
        job = self.wait_for_job(job_spec['uuid'], 'completed')
        self.assertEqual(1, len(job['instances']))
        self.assertEqual('failed', job['instances'][0]['status'])

    def test_get_job(self):
        # schedule a job
        job_spec = self.minimal_job() 
        request_body = {'jobs': [job_spec]}
        resp = self.session.post('%s/rawscheduler' % self.cook_url,
                                 json={'jobs': [job_spec]})
        self.assertEqual(201, resp.status_code)

        # query for the same job & ensure the response has what it's supposed to have
        resp = self.session.get('%s/rawscheduler?job=%s' % (self.cook_url, job_spec['uuid']))
        self.assertEqual(200, resp.status_code)
        job = self.wait_for_job(job_spec['uuid'], 'completed')
        self.assertEquals(job_spec['mem'], job['mem'])
        self.assertEquals(job_spec['max_retries'], job['max_retries'])
        self.assertEquals(job_spec['name'], job['name'])
        self.assertEquals(job_spec['priority'], job['priority'])
        self.assertEquals(job_spec['uuid'], job['uuid'])
        self.assertEquals(job_spec['cpus'], job['cpus'])
        self.assertTrue('labels' in job)
        self.assertEquals(9223372036854775807, job['max_runtime'])
        # 9223372036854775807 is MAX_LONG(ish), the default value for max_runtime
        self.assertEquals('success', job['state'])
        self.assertTrue('env' in job)
        self.assertTrue('framework_id' in job)
        self.assertTrue('ports' in job)
        self.assertTrue('instances' in job)
        self.assertEquals('completed', job['status'])
        self.assertTrue(isinstance(job['submit_time'], int))
        self.assertTrue('uris' in job)
        self.assertTrue('retries_remaining' in job)
        instance = job['instances'][0]
        self.assertTrue(isinstance(instance['start_time'], int))
        self.assertTrue(isinstance(instance['executor_id'], unicode))
        self.assertTrue(isinstance(instance['hostname'], unicode))
        self.assertTrue(isinstance(instance['slave_id'], unicode))
        self.assertTrue(isinstance(instance['preempted'], bool))
        self.assertTrue(isinstance(instance['end_time'], int))
        self.assertTrue(isinstance(instance['backfilled'], bool))
        self.assertTrue('ports' in instance)
        self.assertEquals('completed', job['status'])
        self.assertTrue(isinstance(instance['task_id'], unicode))


    # TODO This method should schedule a job on Cook to determine
    # what Cook thinks the current user is.  The user is used as
    # a query parameter when listing jobs, for example.
    def determine_user(self):
        return "vagrant"

    def test_list_jobs_by_state(self):
        # schedule a bunch of jobs in hopes of getting jobs into different statuses
        request_body = {'jobs': [self.minimal_job(command="sleep %s" % i) for i in range(1,20)]}
        resp = self.session.post('%s/rawscheduler' % self.cook_url, json=request_body)
        self.assertEqual(resp.status_code, 201)

        # let some jobs get scheduled
        time.sleep(10)
        user = self.determine_user()

        for state in ['waiting', 'running', 'completed']:
            resp = self.session.get('%s/list?user=%s&state=%s' % (self.cook_url, user, state))
            self.assertEqual(200, resp.status_code)
            jobs = resp.json()
            for job in jobs:
                #print "%s %s" % (job['uuid'], job['status'])
                self.assertEquals(state, job['status'])

    # load a job by UUID using GET /rawscheduler
    def get_job(self, uuid):
        return self.session.get('%s/rawscheduler?job=%s' % (self.cook_url, uuid)).json()[0]

    def test_list_jobs_by_time(self):
        # schedule two jobs with different submit times
        job_specs = [self.minimal_job() for _ in range(2)];

        request_body = {'jobs': [job_specs[0]]}
        resp = self.session.post('%s/rawscheduler' % self.cook_url, json=request_body)
        self.assertEqual(resp.status_code, 201)

        time.sleep(1)

        request_body = {'jobs': [job_specs[1]]}
        resp = self.session.post('%s/rawscheduler' % self.cook_url, json=request_body)
        self.assertEqual(resp.status_code, 201)

        submit_times = [self.get_job(job_spec['uuid'])['submit_time'] for job_spec in job_specs]

        user = self.determine_user()

        # start-ms and end-ms are exclusive

        # query where start-ms and end-ms are the submit times of jobs 1 & 2 respectively
        resp = self.session.get('%s/list?user=%s&state=waiting&start-ms=%s&end-ms=%s'
                % (self.cook_url, user, submit_times[0]-1, submit_times[1]+1))
        self.assertEqual(200, resp.status_code)
        jobs = resp.json()
        self.assertTrue(any(job for job in jobs if job['uuid'] == job_specs[0]['uuid']))
        self.assertTrue(any(job for job in jobs if job['uuid'] == job_specs[1]['uuid']))

        # query just for job 1
        resp = self.session.get('%s/list?user=%s&state=waiting&start-ms=%s&end-ms=%s'
                % (self.cook_url, user, submit_times[0]-1, submit_times[1]))
        self.assertEqual(200, resp.status_code)
        jobs = resp.json()
        self.assertTrue(any(job for job in jobs if job['uuid'] == job_specs[0]['uuid']))
        self.assertFalse(any(job for job in jobs if job['uuid'] == job_specs[1]['uuid']))

        # query just for job 2
        resp = self.session.get('%s/list?user=%s&state=waiting&start-ms=%s&end-ms=%s'
                % (self.cook_url, user, submit_times[0], submit_times[1]+1))
        self.assertEqual(200, resp.status_code)
        jobs = resp.json()
        self.assertFalse(any(job for job in jobs if job['uuid'] == job_specs[0]['uuid']))
        self.assertTrue(any(job for job in jobs if job['uuid'] == job_specs[1]['uuid']))

        # query for neither
        resp = self.session.get('%s/list?user=%s&state=waiting&start-ms=%s&end-ms=%s'
                % (self.cook_url, user, submit_times[0], submit_times[1]))
        self.assertEqual(200, resp.status_code)
        jobs = resp.json()
        self.assertFalse(any(job for job in jobs if job['uuid'] == job_specs[0]['uuid']))
        self.assertFalse(any(job for job in jobs if job['uuid'] == job_specs[1]['uuid']))

    def test_cancel_job(self):
        job_spec = self.minimal_job(command='sleep 300')
        resp = self.session.post('%s/rawscheduler' % self.cook_url,
                                 json={'jobs': [job_spec]})
        self.wait_for_job(job_spec['uuid'], 'running')
        resp = self.session.delete(
            '%s/rawscheduler?job=%s' % (self.cook_url, job_spec['uuid']))
        self.assertEqual(204, resp.status_code)
        job = self.session.get(
            '%s/rawscheduler?job=%s' % (self.cook_url, job_spec['uuid'])).json()[0]
        self.assertEqual('failed', job['state'])
