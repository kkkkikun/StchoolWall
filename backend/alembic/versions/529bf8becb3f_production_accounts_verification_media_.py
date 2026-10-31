"""production_accounts_verification_media_jobs

Revision ID: 529bf8becb3f
Revises: a7b8c9d0e1f2
Create Date: 2026-10-16 18:09:22.456881

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '529bf8becb3f'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Old credentials must never regain production authorization after this cutover.
    op.create_table('jobs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=50), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('dedupe_key', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('lease_token', sa.UUID(), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dedupe_key')
    )
    op.create_index('ix_jobs_claim', 'jobs', ['status', 'available_at'], unique=False)
    op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'], unique=False)
    op.create_table('appeals',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=20), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('decision_reason', sa.Text(), nullable=True),
    sa.Column('handled_by', sa.String(length=36), nullable=True),
    sa.Column('handled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_appeals_status'), 'appeals', ['status'], unique=False)
    op.create_index(op.f('ix_appeals_user_id'), 'appeals', ['user_id'], unique=False)
    op.create_index('uq_appeals_pending_entity', 'appeals', ['user_id', 'entity_type', 'entity_id'], unique=True, postgresql_where=sa.text("status = 'pending'"))
    op.create_table('login_identities',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('subject', sa.String(length=128), nullable=False),
    sa.Column('password_hash', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'subject', name='uq_identity_provider_subject')
    )
    op.create_index(op.f('ix_login_identities_user_id'), 'login_identities', ['user_id'], unique=False)
    op.create_table('media_assets',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('purpose', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('storage_key', sa.String(length=255), nullable=False),
    sa.Column('public_path', sa.String(length=255), nullable=True),
    sa.Column('content_type', sa.String(length=50), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=20), nullable=True),
    sa.Column('entity_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('storage_key')
    )
    op.create_index(op.f('ix_media_assets_entity_id'), 'media_assets', ['entity_id'], unique=False)
    op.create_index(op.f('ix_media_assets_entity_type'), 'media_assets', ['entity_type'], unique=False)
    op.create_index(op.f('ix_media_assets_owner_id'), 'media_assets', ['owner_id'], unique=False)
    op.create_index(op.f('ix_media_assets_status'), 'media_assets', ['status'], unique=False)
    op.create_table('pairing_codes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code_hash')
    )
    op.create_index(op.f('ix_pairing_codes_user_id'), 'pairing_codes', ['user_id'], unique=False)
    op.create_table('recovery_codes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code_hash')
    )
    op.create_index(op.f('ix_recovery_codes_user_id'), 'recovery_codes', ['user_id'], unique=False)
    op.create_table('student_identity_claims',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('school_id', sa.String(length=64), nullable=False),
    sa.Column('student_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('fingerprint_key_version', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('school_id', 'student_fingerprint', name='uq_student_claim_school_fingerprint'),
    sa.UniqueConstraint('school_id', 'user_id', name='uq_student_claim_school_user')
    )
    op.create_index(op.f('ix_student_identity_claims_user_id'), 'student_identity_claims', ['user_id'], unique=False)
    op.create_table('student_verification_challenges',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=8), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_student_verification_challenges_user_id'), 'student_verification_challenges', ['user_id'], unique=False)
    op.create_table('user_blocks',
    sa.Column('blocker_id', sa.UUID(), nullable=False),
    sa.Column('blocked_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.CheckConstraint('blocker_id <> blocked_id', name='ck_user_blocks_not_self'),
    sa.ForeignKeyConstraint(['blocked_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['blocker_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('blocker_id', 'blocked_id')
    )
    op.create_index(op.f('ix_user_blocks_blocked_id'), 'user_blocks', ['blocked_id'], unique=False)
    op.create_table('student_verifications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('challenge_id', sa.UUID(), nullable=False),
    sa.Column('school_id', sa.String(length=64), nullable=False),
    sa.Column('student_fingerprint', sa.String(length=64), nullable=True),
    sa.Column('fingerprint_key_version', sa.String(length=32), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('consent_version', sa.String(length=32), nullable=True),
    sa.Column('consented_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('proof_key', sa.String(length=255), nullable=True),
    sa.Column('card_valid_until', sa.Date(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reviewed_by', sa.String(length=36), nullable=True),
    sa.Column('review_reason', sa.Text(), nullable=True),
    sa.Column('verified_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('evidence_delete_after', sa.DateTime(timezone=True), nullable=True),
    sa.Column('evidence_deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['challenge_id'], ['student_verification_challenges.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('challenge_id')
    )
    op.create_index(op.f('ix_student_verifications_evidence_delete_after'), 'student_verifications', ['evidence_delete_after'], unique=False)
    op.create_index(op.f('ix_student_verifications_status'), 'student_verifications', ['status'], unique=False)
    op.create_index(op.f('ix_student_verifications_user_id'), 'student_verifications', ['user_id'], unique=False)
    op.create_index('uq_student_verifications_pending_user', 'student_verifications', ['user_id'], unique=True, postgresql_where=sa.text("status = 'pending'"))
    op.create_table('user_sessions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('identity_id', sa.UUID(), nullable=True),
    sa.Column('refresh_hash', sa.String(length=64), nullable=False),
    sa.Column('previous_refresh_hash', sa.String(length=64), nullable=True),
    sa.Column('client_type', sa.String(length=16), nullable=False),
    sa.Column('token_version', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['identity_id'], ['login_identities.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('refresh_hash')
    )
    op.create_index(op.f('ix_user_sessions_previous_refresh_hash'), 'user_sessions', ['previous_refresh_hash'], unique=False)
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
    op.create_table('spent_refresh_tokens',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('session_id', sa.UUID(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['user_sessions.id'], ),
    sa.PrimaryKeyConstraint('token_hash')
    )
    op.create_index(op.f('ix_spent_refresh_tokens_expires_at'), 'spent_refresh_tokens', ['expires_at'], unique=False)
    op.create_index(op.f('ix_spent_refresh_tokens_session_id'), 'spent_refresh_tokens', ['session_id'], unique=False)
    op.execute('UPDATE activities SET status = 1 WHERE status IS NULL')
    op.alter_column('activities', 'status',
               existing_type=sa.SMALLINT(),
               nullable=False)
    op.add_column('admin_users', sa.Column('mfa_secret_encrypted', sa.String(length=255), nullable=True))
    op.add_column('admin_users', sa.Column('mfa_last_counter', sa.Integer(), nullable=True))
    op.drop_constraint('admin_users_username_key', 'admin_users', type_='unique')
    op.drop_index('ix_admin_users_username', table_name='admin_users')
    op.create_index(op.f('ix_admin_users_username'), 'admin_users', ['username'], unique=True)
    op.execute('UPDATE banners SET sort = 0 WHERE sort IS NULL')
    op.execute('UPDATE banners SET status = 1 WHERE status IS NULL')
    op.alter_column('banners', 'sort',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('banners', 'status',
               existing_type=sa.SMALLINT(),
               nullable=False)
    op.execute('''DELETE FROM footprints WHERE id IN (
        SELECT id FROM (SELECT id, row_number() OVER (
            PARTITION BY user_id, post_id ORDER BY viewed_at DESC NULLS LAST, id DESC
        ) AS duplicate_number FROM footprints) ranked WHERE duplicate_number > 1
    )''')
    op.create_unique_constraint('uq_footprints_user_post', 'footprints', ['user_id', 'post_id'])
    op.drop_constraint('notifications_post_id_fkey', 'notifications', type_='foreignkey')
    op.alter_column('reports', 'handled_by',
               existing_type=sa.UUID(),
               type_=sa.String(length=36),
               existing_nullable=True)
    op.add_column('users', sa.Column('verified_until', sa.DateTime(timezone=True), nullable=True))
    # Backfill only provable legacy identities, without merging any users.
    op.execute("""INSERT INTO login_identities(id, user_id, provider, subject, password_hash)
        SELECT md5('schoolwall:password:' || id::text)::uuid, id, 'password',
               substring(openid from 5), web_password_hash
        FROM users WHERE openid LIKE 'web:%' AND status = 1
        ON CONFLICT (provider, subject) DO NOTHING""")
    from app.config import settings
    for provider, app_id, prefix in (
        ("weixin", settings.WECHAT_APP_ID, ""),
        ("mp", settings.WECHAT_MP_APP_ID, "mp:"),
    ):
        if not app_id:
            continue  # Lazy identity import uses the configured AppID on next successful login.
        statement = sa.text("""INSERT INTO login_identities(id, user_id, provider, subject)
            SELECT md5(:provider || id::text)::uuid, id, :provider,
                   substring(openid from :offset)
            FROM users WHERE status = 1 AND
                CASE WHEN :prefix = '' THEN openid NOT LIKE 'web:%' AND openid NOT LIKE 'mp:%'
                    AND openid NOT LIKE 'dev_%' AND openid NOT LIKE 'system:%'
                ELSE openid LIKE 'mp:%' END
            ON CONFLICT (provider, subject) DO NOTHING""").bindparams(
                sa.bindparam("provider", provider + ":" + app_id),
                sa.bindparam("offset", len(prefix) + 1),
                sa.bindparam("prefix", prefix))
        op.execute(statement)
    op.execute("""UPDATE users SET is_verified = false, verified_until = NULL,
        student_id = NULL, real_name = NULL,
        role = CASE WHEN role IN ('student', 'admin') THEN 'guest' ELSE role END""")
    op.execute("""UPDATE users SET status = -2, web_password_hash = NULL
        WHERE openid IN ('dev_demo_admin', 'dev_demo_student')""")


def downgrade() -> None:
    # Old credentials must never regain production authorization after this cutover.
    op.drop_column('users', 'verified_until')
    op.alter_column('reports', 'handled_by',
               existing_type=sa.String(length=36),
               type_=sa.UUID(),
               postgresql_using='handled_by::uuid',
               existing_nullable=True)
    op.execute('UPDATE notifications SET post_id = NULL WHERE post_id NOT IN (SELECT id FROM posts)')
    op.create_foreign_key('notifications_post_id_fkey', 'notifications', 'posts', ['post_id'], ['id'])
    op.drop_constraint('uq_footprints_user_post', 'footprints', type_='unique')
    op.alter_column('banners', 'status',
               existing_type=sa.SMALLINT(),
               nullable=True)
    op.execute('UPDATE banners SET sort = 0 WHERE sort IS NULL')
    op.execute('UPDATE banners SET status = 1 WHERE status IS NULL')
    op.alter_column('banners', 'sort',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_index(op.f('ix_admin_users_username'), table_name='admin_users')
    op.create_index('ix_admin_users_username', 'admin_users', ['username'], unique=False)
    op.create_unique_constraint('admin_users_username_key', 'admin_users', ['username'])
    op.drop_column('admin_users', 'mfa_last_counter')
    op.drop_column('admin_users', 'mfa_secret_encrypted')
    op.execute('UPDATE activities SET status = 1 WHERE status IS NULL')
    op.alter_column('activities', 'status',
               existing_type=sa.SMALLINT(),
               nullable=True)
    op.drop_index(op.f('ix_spent_refresh_tokens_session_id'), table_name='spent_refresh_tokens')
    op.drop_index(op.f('ix_spent_refresh_tokens_expires_at'), table_name='spent_refresh_tokens')
    op.drop_table('spent_refresh_tokens')
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_previous_refresh_hash'), table_name='user_sessions')
    op.drop_table('user_sessions')
    op.drop_index('uq_student_verifications_pending_user', table_name='student_verifications', postgresql_where=sa.text("status = 'pending'"))
    op.drop_index(op.f('ix_student_verifications_user_id'), table_name='student_verifications')
    op.drop_index(op.f('ix_student_verifications_status'), table_name='student_verifications')
    op.drop_index(op.f('ix_student_verifications_evidence_delete_after'), table_name='student_verifications')
    op.drop_table('student_verifications')
    op.drop_index(op.f('ix_user_blocks_blocked_id'), table_name='user_blocks')
    op.drop_table('user_blocks')
    op.drop_index(op.f('ix_student_verification_challenges_user_id'), table_name='student_verification_challenges')
    op.drop_table('student_verification_challenges')
    op.drop_index(op.f('ix_student_identity_claims_user_id'), table_name='student_identity_claims')
    op.drop_table('student_identity_claims')
    op.drop_index(op.f('ix_recovery_codes_user_id'), table_name='recovery_codes')
    op.drop_table('recovery_codes')
    op.drop_index(op.f('ix_pairing_codes_user_id'), table_name='pairing_codes')
    op.drop_table('pairing_codes')
    op.drop_index(op.f('ix_media_assets_status'), table_name='media_assets')
    op.drop_index(op.f('ix_media_assets_owner_id'), table_name='media_assets')
    op.drop_index(op.f('ix_media_assets_entity_type'), table_name='media_assets')
    op.drop_index(op.f('ix_media_assets_entity_id'), table_name='media_assets')
    op.drop_table('media_assets')
    op.drop_index(op.f('ix_login_identities_user_id'), table_name='login_identities')
    op.drop_table('login_identities')
    op.drop_index('uq_appeals_pending_entity', table_name='appeals', postgresql_where=sa.text("status = 'pending'"))
    op.drop_index(op.f('ix_appeals_user_id'), table_name='appeals')
    op.drop_index(op.f('ix_appeals_status'), table_name='appeals')
    op.drop_table('appeals')
    op.drop_index(op.f('ix_jobs_status'), table_name='jobs')
    op.drop_index('ix_jobs_claim', table_name='jobs')
    op.drop_table('jobs')
