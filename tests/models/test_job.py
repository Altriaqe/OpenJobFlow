from jobflow.models.job import JobRecord


def test_job_record_stores_standard_fields() -> None:
    source = "test_source"
    external_id = "test_external_id"
    title = "test_title"
    company = "test_company"
    city = "test_city"
    detail_url = "http://example.com/jobs/job-1"

    record = JobRecord(
        source=source,
        external_id=external_id,
        title=title,
        company=company,
        city=city,
        detail_url=detail_url,
    )

    assert record.source == source
    assert record.external_id == external_id
    assert record.title == title
    assert record.company == company
    assert record.city == city
    assert record.detail_url == detail_url
