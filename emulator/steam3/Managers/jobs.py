import time
from datetime import datetime
from typing import Callable, Dict, Optional


class Job:
    """Represents a single server-side job."""
    job_id_counter = 1  # Static counter for job IDs

    def __init__(self, name: str, start_param: Optional[dict] = None):
        self.job_id = Job.job_id_counter
        Job.job_id_counter += 1
        self.name = name
        self.start_param = start_param
        self.creation_time = datetime.now()
        self.is_running = False

    def start(self):
        """Simulates starting a job."""
        self.is_running = True
        print(f"[{self._get_timestamp()}] Job {self.job_id} - {self.name} started with param: {self.start_param}")

    def stop(self):
        """Simulates stopping a job."""
        self.is_running = False
        print(f"[{self._get_timestamp()}] Job {self.job_id} - {self.name} stopped.")

    @staticmethod
    def _get_timestamp() -> str:
        """Returns the current timestamp in the specified format."""
        return datetime.now().strftime("%m/%d/%Y %H:%M:%S")


class JobManager:
    """Manages the lifecycle of jobs."""
    def __init__(self):
        self.jobs: Dict[int, Job] = {}  # Maps job IDs to Job instances
        self.job_types: Dict[str, Callable[[Optional[dict]], Job]] = {}  # Maps job names to creation functions

    def register_job_type(self, job_name: str, creation_func: Callable[[Optional[dict]], Job]):
        """Registers a job type with a factory function."""
        self.job_types[job_name] = creation_func
        print(f"[{self._get_timestamp()}] Registered job type: {job_name}")

    def create_job(self, job_name: str, start_param: Optional[dict] = None) -> Optional[Job]:
        """Creates a new job of the given type."""
        if job_name not in self.job_types:
            print(f"[{self._get_timestamp()}] Error: Job type '{job_name}' is not registered.")
            return None

        job = self.job_types[job_name](start_param)
        self.jobs[job.job_id] = job
        job.start()
        return job

    def cancel_job(self, job_id: int):
        """Stops and removes a job by its ID."""
        job = self.jobs.pop(job_id, None)
        if not job:
            print(f"[{self._get_timestamp()}] Error: No job found with ID {job_id}")
            return

        job.stop()
        print(f"[{self._get_timestamp()}] Job {job_id} canceled and removed.")

    def run_jobs(self):
        """Simulates running all jobs."""
        for job in self.jobs.values():
            if job.is_running:
                print(f"[{self._get_timestamp()}] Running job {job.job_id} - {job.name}")

    @staticmethod
    def _get_timestamp() -> str:
        """Returns the current timestamp in the specified format."""
        return datetime.now().strftime("%m/%d/%Y %H:%M:%S")


# Example usage
if __name__ == "__main__":
    # Create a job manager
    manager = JobManager()

    # Register a couple of job types
    manager.register_job_type("ExampleJob", lambda param: Job("ExampleJob", param))
    manager.register_job_type("AnotherJob", lambda param: Job("AnotherJob", param))

    # Create and manage jobs
    job1 = manager.create_job("ExampleJob", {"param": "value1"})
    job2 = manager.create_job("AnotherJob", {"param": "value2"})

    # Simulate running jobs
    manager.run_jobs()

    # Cancel a job
    if job1:
        manager.cancel_job(job1.job_id)

    # Run remaining jobs
    manager.run_jobs()