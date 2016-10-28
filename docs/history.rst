.. :changelog:

Version History
===============

Next Release
------------
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
