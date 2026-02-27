INSERT INTO role_assignments (
    id,
    user_id,
    business_unit_id,
    role,
    active,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid(),
    u.id,
    NULL,
    'super_admin'::role_type,
    TRUE,
    now(),
    now()
FROM users u
WHERE u.email = 'dev.user@local.test'
  AND NOT EXISTS (
      SELECT 1
      FROM role_assignments ra
      WHERE ra.user_id = u.id
        AND ra.role = 'super_admin'::role_type
        AND ra.business_unit_id IS NULL
  );
