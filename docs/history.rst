.. :changelog:

Version History
===============

1.5.1 (2019-06-05)
------------------
- Fix refreshing of local credentials on failure, streamline logic

1.5.0 (2019-06-04)
------------------
- Add support for ``aws_security_token``/``aws_ssion_token``/``expiration`` in configuration files
- Add support for ``AWS_SECURITY_TOKEN``/``AWS_SESSION_TOKEN`` environment variable config

1.4.0 (2019-05-08)
------------------
- Add support for credentials files when refreshing credentials

1.3.0 (2019-02-11)
------------------
- Add support for Python 3.7
- Drop support for versions of tornado < 5.0

1.2.0 (2018-10-12)
------------------
- Add ``force_instance`` option when creating the client to disable instance isolation (#8)
- Fix a bug where we assume amz-jz error responses will include a message

1.1.1 (2018-06-16)
------------------
- Don't convert str to bytes in Python 2 when making headers

1.1.0 (2018-03-19)
------------------
 - Add ``close`` method to ``AWSClient`` (#9 from `31z4 <https://github.com/31z4>_`)

1.0.0 (2018-01-19)
------------------
 - Add new exception type ``tornado_aws.exceptions.RequestException`` (#5 from `nvllsvm <https://github.com/nvllsvm>_`)
 - Mark as stable in Trove classifiers

0.8.0 (2017-06-06)
------------------
 - Rework error processing to support ``application/json``,
    ``application/x-amz-json-1.0``, ``application/x-amz-json-1.0`` and
    XML based responses (S3, E2, others)
 - Move to 100% test coverage \o/

0.7.3 (2017-06-06)
------------------
 - The error was introduced in 0.7.1, redeclaring ``error``. Fix that.

0.7.2 (2017-06-06)
------------------
 - What type of error is it if it has no response? Odd.

0.7.1 (2017-06-05)
------------------
 - Getting error response back that we can't decode, log it

0.7.0 (2017-06-02)
------------------
 - Don't overwrite the ``Host`` HTTP header if it's set
 - Change fetch body arg default to None

0.6.0 (2017-04-18)
------------------
 - Add support for using ``curl_httpclient.CurlAsyncHTTPClient``

0.5.0 (2016-10-28)
------------------
 - Correctly support region lookup for non-default profiles.

0.4.4 (2016-04-01)
------------------
 - Don't blow up if awz_error does not have a message

0.4.3 (2016-04-01)
------------------
 - Allow GET with empty body (#2) - Dmitry Mukhin
 - Ensure headers is None if empty (#2) - Dmitry Mukhin
 - Don't blow up if an exception other than tornado.httpclient.HTTPError is raised

0.4.2 (2016-02-16)
------------------
 - Add support for ``ExpiredTokenException``

0.4.1 (2016-02-16)
------------------
 - Pass in kwargs into ``AWSClientException``

0.4.0 (2016-02-05)
------------------
 - Add support for the AWS_DEFAULT_REGION environment variable
 - Cleanup retry requests
 - Ensure HTTPClient usage is new and not out of a shared pool

0.3.0 (2016-02-03)
------------------
 - Make authentication work with EC2 Instance metadata, add async support for credential fetching

0.2.0 (2016-02-02)
------------------
 - Add support for fetching credentials and region from EC2 Instance metadata

0.1.0 (2015-10-22)
------------------
 - Initial Release
