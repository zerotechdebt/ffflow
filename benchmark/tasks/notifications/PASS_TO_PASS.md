# Regression gate (pass_to_pass)

Run the project's own suite under pytest:
  DEBUG=true DATABASE_URL=':memory:' python -m pytest apps/accounts/tests.py apps/articles/tests.py apps/comments/tests.py -q

Baseline on untouched repo: **107 passed, 1 failed**.
The 1 pre-existing failure is EXCLUDED from the gate:
  apps/accounts/tests.py::UserIdentityPropertyTest::test_authentication_always_keyed_on_email_not_username

PASS = the 107 previously-passing tests still pass after the agent's change.
(Only arm C ships this suite; arm A has no tests.py, so for A the regression
gate is the subset of these behaviors re-expressed in the fail_to_pass-neutral
checks. For the A/C comparison we run C's suite against BOTH arms' final trees.)
