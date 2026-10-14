package ma.inpt.cloud.user;

/**
 * Represents the lifecycle states of a user account.
 *
 * <ul>
 *   <li>{@link #PENDING_VERIFICATION} – Account created but email not yet verified.</li>
 *   <li>{@link #ACTIVE}               – Account is fully operational.</li>
 *   <li>{@link #SUSPENDED}            – Account suspended by an administrator.</li>
 *   <li>{@link #LOCKED}               – Account temporarily locked after too many failed logins.</li>
 * </ul>
 */
public enum AccountStatus {

    /** Account created; awaiting email/identity verification. */
    PENDING_VERIFICATION,

    /** Account is active and the user may log in. */
    ACTIVE,

    /** Account has been suspended by an administrator. */
    SUSPENDED,

    /** Account is temporarily locked due to excessive failed login attempts. */
    LOCKED
}
