from scanservice.jenkins import JenkinsClient


def test_discover_jobs_recurses_through_folders():
    client = JenkinsClient("http://jenkins")
    listings = {
        "packages": [
            {"name": "curl", "_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob"},
            {"name": "system", "_class": "com.cloudbees.hudson.plugins.folder.Folder"},
        ],
        "packages/system": [
            {"name": "openssl", "_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob"},
        ],
    }
    client.list_jobs = lambda folder="": listings[folder]

    try:
        assert client.discover_jobs(("packages",)) == [
            "packages/curl",
            "packages/system/openssl",
        ]
    finally:
        client.close()
