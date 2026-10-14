package ma.inpt.cloud.auth.service;

import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.inpt.cloud.auth.dto.LoginRequest;
import ma.inpt.cloud.auth.dto.RegisterRequest;
import ma.inpt.cloud.user.AccountStatus;
import ma.inpt.cloud.user.User;
import ma.inpt.cloud.user.UserRepository;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

/**
 * Core authentication service.
 *
 * <p>This service is responsible for:
 * <ol>
 *   <li>Enforcing per-(IP, email) rate limits via {@link RateLimitService}.</li>
 *   <li>Verifying user credentials in a timing-attack-resistant way.</li>
 *   <li>Checking that the account is {@link AccountStatus#ACTIVE}.</li>
 *   <li>Managing the HTTP session on successful login.</li>
 *   <li>Invalidating the session on logout.</li>
 *   <li>Registering new user accounts with basic safety checks.</li>
 * </ol>
 *
 * <h3>Timing-attack resistance</h3>
 * <p>When the requested email does not exist, the service still runs a full
 * Argon2id hash computation against a dummy password.  This equalises the
 * response time between "user not found" and "wrong password", preventing an
 * attacker from enumerating valid email addresses via response latency.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    /** Session attribute key that stores the authenticated user's UUID. */
    public static final String SESSION_USER_ID_KEY = "USER_ID";

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final RateLimitService rateLimitService;

    // ── Public methods ────────────────────────────────────────────────────

    /**
     * Registers a new user account.
     *
     * <p>Registration rules:
     * <ul>
     *   <li>The email is normalised (trimmed + lowercased) before any check.</li>
     *   <li>If the email is already taken, a {@link RuntimeException} with the
     *       message {@code "Email already in use"} is thrown.</li>
     *   <li>If the raw password contains the local-part of the email (the portion
     *       before {@code @}), a {@link RuntimeException} with the message
     *       {@code "Password too similar to email"} is thrown.</li>
     *   <li>The password is encoded with the configured {@link PasswordEncoder}
     *       before persistence.</li>
     *   <li>The new account is created with status {@link AccountStatus#ACTIVE}
     *       (no email-verification flow for demo purposes).</li>
     * </ul>
     *
     * @param req the validated registration request (email + raw password)
     * @return the newly created user's normalised email address
     * @throws RuntimeException if the email is already in use or the password is
     *                          too similar to the email
     */
    @Transactional
    public String register(RegisterRequest req) {

        // 1. Normalise email ───────────────────────────────────────────────
        String normalizedEmail = req.email().trim().toLowerCase();

        // 2. Duplicate-email check ─────────────────────────────────────────
        if (userRepository.findByEmailIgnoreCase(normalizedEmail).isPresent()) {
            log.warn("Registration rejected: email already in use — {}", normalizedEmail);
            throw new RuntimeException("Email already in use");
        }

        // 3. Password similarity check ─────────────────────────────────────
        //    Extract the local-part (before '@') and verify the password does
        //    not contain it (case-insensitive comparison).
        String emailPrefix = normalizedEmail.contains("@")
                ? normalizedEmail.substring(0, normalizedEmail.indexOf('@'))
                : normalizedEmail;

        if (req.password().toLowerCase().contains(emailPrefix)) {
            log.warn("Registration rejected: password too similar to email — {}", normalizedEmail);
            throw new RuntimeException("Password too similar to email");
        }

        // 4. Encode password ───────────────────────────────────────────────
        String encodedPassword = passwordEncoder.encode(req.password());

        // 5. Build and persist the new user ───────────────────────────────
        User newUser = new User();
        newUser.setEmail(normalizedEmail);
        newUser.setPasswordHash(encodedPassword);
        newUser.setStatus(AccountStatus.ACTIVE); // demo: skip email-verification
        newUser.setFailedLoginAttempts(0);

        User saved = userRepository.save(newUser);
        log.info("New user registered: userId={} email={}", saved.getId(), saved.getEmail());

        return saved.getEmail();
    }

    /**
     * Authenticates a user and binds them to the provided HTTP session.
     *
     * @param req      the validated login request (email + raw password)
     * @param clientIp the client's remote IP address (used for rate limiting)
     * @param session  the current HTTP session
     * @return the authenticated user's normalised email address
     * @throws RuntimeException if the rate limit is exceeded, credentials are invalid,
     *                          or the account is not active
     */
    @Transactional
    public String login(LoginRequest req, String clientIp, HttpSession session) {

        // 1. Rate-limit check ──────────────────────────────────────────────
        String normalizedEmail = req.email().trim().toLowerCase();
        if (!rateLimitService.isAllowed(clientIp, normalizedEmail)) {
            log.warn("Rate limit exceeded for ip={} email={}", clientIp, normalizedEmail);
            throw new RuntimeException("Too many requests");
        }

        // 2. Load user (Optional — may be empty) ──────────────────────────
        Optional<User> userOpt = userRepository.findByEmailIgnoreCase(normalizedEmail);

        // 3. Credential verification ───────────────────────────────────────
        //    We ALWAYS run a hash comparison (against a dummy hash when the user
        //    does not exist) to prevent timing-based user enumeration.
        boolean passwordMatches;
        if (userOpt.isPresent()) {
            passwordMatches = passwordEncoder.matches(req.password(), userOpt.get().getPasswordHash());
        } else {
            // Dummy hash: same Argon2id cost as a real hash.
            // The result is discarded; we just need the CPU time to elapse.
            passwordEncoder.encode("dummy-password-to-prevent-timing-attack");
            passwordMatches = false;
        }

        if (!passwordMatches) {
            log.debug("Failed login attempt for email={}", normalizedEmail);
            throw new RuntimeException("Invalid credentials");
        }

        // At this point userOpt is guaranteed to be present (passwordMatches = true).
        User user = userOpt.get();

        // 4. Account status guard ──────────────────────────────────────────
        if (user.getStatus() != AccountStatus.ACTIVE) {
            log.warn("Login rejected: account not active. userId={} status={}", user.getId(), user.getStatus());
            throw new RuntimeException("Account not active");
        }

        // 5. Success: reset failed attempts counter ────────────────────────
        user.setFailedLoginAttempts(0);
        user.setLockoutUntil(null);
        userRepository.save(user);

        // 6. Bind user to session ─────────────────────────────────────────
        //    Spring Session (Redis-backed) will persist this attribute.
        //    We store the UUID string so the session attribute is serialisation-safe.
        session.setAttribute(SESSION_USER_ID_KEY, user.getId().toString());
        log.info("Successful login for userId={}", user.getId());

        return user.getEmail();
    }

    /**
     * Logs the user out by invalidating their HTTP session.
     *
     * @param session the session to invalidate
     */
    public void logout(HttpSession session) {
        session.invalidate();
        log.debug("Session invalidated");
    }
}
