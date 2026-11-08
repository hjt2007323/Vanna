# G1 Vanna SQLite: baseline run

Generated: 20261107T133321Z

counts: {'cases': 29, 'meets_expectation': 7, 'rows_ok': 13, 'errors': 4, 'unsupported': 12}

| case | category | result | expectation |
|---|---|---|---|
| V0_normal_select | normal_read | 2 rows ['id', 'name', 'price'] | PASS |
| V1_leading_comment_select | query_compat | rows_affected=-1 | FAIL |
| V2_with_select | query_compat | rows_affected=-1 | FAIL |
| V3_values | query_compat | rows_affected=-1 | FAIL |
| V4_empty_result_columns | empty_result | 0 rows [] | FAIL |
| V4b_empty_table | empty_result | 0 rows [] | FAIL |
| V5_default_insert_commit | default_write | rows_affected=1 | PASS |
| V5b_default_update_commit | default_write | rows_affected=1 | PASS |
| V6_insert_returning | returning | error: OperationalError: cannot commit transaction - SQL statements in progress | FAIL |
| V6b_update_returning | returning | error: OperationalError: cannot commit transaction - SQL statements in progress | FAIL |
| V6c_returning_zero_rows | returning | rows_affected=0 | FAIL |
| V7a_readonly_insert | read_only | unsupported: TypeError | FAIL |
| V7b_readonly_cte_delete | read_only | unsupported: TypeError | FAIL |
| V7c_readonly_attach | read_only | unsupported: TypeError | FAIL |
| V7d_readonly_pragma_write | read_only | unsupported: TypeError | FAIL |
| V7e_readonly_pragma_read | read_only | unsupported: TypeError | FAIL |
| V7f_readonly_ddl | read_only | unsupported: TypeError | FAIL |
| V7g_readonly_load_extension | read_only | unsupported: TypeError | FAIL |
| V7h_readonly_vacuum_into | read_only | unsupported: TypeError | FAIL |
| V7i_readonly_journal_mode | read_only | unsupported: TypeError | FAIL |
| V7j_readonly_reindex | read_only | unsupported: TypeError | FAIL |
| V8a_space_hash_path_select | path | 2 rows ['id', 'name'] | PASS |
| V8b_space_hash_path_readonly | path | unsupported: TypeError | FAIL |
| V8c_readonly_missing_db | path | unsupported: TypeError | FAIL |
| V9_error_then_delete | lifecycle | error: OperationalError: no such table: table_that_does_not_exist | PASS |
| V10_empty_sql | compat | error: IndexError: list index out of range | PASS |
| V11_delete_rows_affected | default_write | rows_affected=1 | PASS |
| V12_duplicate_column_names | compat | 1 rows ['k'] | FAIL |
| V13_default_pragma_rows | compat | rows_affected=-1 | FAIL |
