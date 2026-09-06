from tests.test_write_reliability import TestWriteReliability
t = TestWriteReliability("test_e14_cli1_no_write_retry")
t.setUp()
print(t.dispatcher.router.worker_status)
