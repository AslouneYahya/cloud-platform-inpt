package ma.inpt.cloud.user;

import com.github.f4b6a3.uuid.UuidCreator;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Persistent entity representing a platform user.
 *
 * <p>UUIDs are generated using the time-ordered UUIDv7 algorithm via
 * {@code uuid-creator}, which provides monotonically increasing IDs that
 * are index-friendly in PostgreSQL.
 *
 * <p>Passwords are stored as Argon2id hashes; the raw password is never
 * persisted here.
 */
@Entity
@Table(
    name = "users",
    indexes = {
        @Index(name = "idx_users_email", columnList = "email", unique = true)
    }
)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class User {

    // ── Identity ──────────────────────────────────────────────────────────

    /**
     * Primary key: UUIDv7 generated before first persistence.
     * UUIDv7 is time-ordered, making it far more efficient than random UUIDv4
     * for B-tree indexes in PostgreSQL.
     */
    @Id
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    // ── Credentials ───────────────────────────────────────────────────────

    /** Unique, case-insensitive email address. Stored in lower-case. */
    @Column(name = "email", nullable = false, unique = true, length = 254)
    private String email;

    /** Argon2id hash of the user's password. Never the raw password. */
    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    // ── Account state ─────────────────────────────────────────────────────

    /**
     * Current lifecycle status of the account.
     * Defaults to {@link AccountStatus#PENDING_VERIFICATION} so newly created
     * accounts cannot log in until they are verified.
     */
    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 30)
    @Builder.Default
    private AccountStatus status = AccountStatus.PENDING_VERIFICATION;

    /**
     * Counter of consecutive failed login attempts.
     * Reset to 0 on a successful login.
     */
    @Column(name = "failed_login_attempts", nullable = false)
    @Builder.Default
    private int failedLoginAttempts = 0;

    /**
     * When the account lockout expires.
     * {@code null} means the account is not currently locked.
     */
    @Column(name = "lockout_until")
    private LocalDateTime lockoutUntil;

    // ── Audit timestamps ──────────────────────────────────────────────────

    /** Automatically set to the instant the row is first inserted. */
    @CreationTimestamp
    @Column(name = "created_at", updatable = false, nullable = false)
    private LocalDateTime createdAt;

    /** Automatically updated to the instant the row is last modified. */
    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    // ── Lifecycle callbacks ───────────────────────────────────────────────

    /**
     * Generates a UUIDv7 primary key before the entity is first persisted.
     * This runs inside the same transaction as the INSERT.
     */
    @PrePersist
    private void prePersist() {
        if (this.id == null) {
            this.id = UuidCreator.getTimeOrderedEpoch(); // UUIDv7
        }
    }
}
