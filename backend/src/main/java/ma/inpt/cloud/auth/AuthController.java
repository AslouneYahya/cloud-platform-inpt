package ma.inpt.cloud.auth;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.inpt.cloud.auth.dto.ApiResponse;
import ma.inpt.cloud.auth.dto.LoginRequest;
import ma.inpt.cloud.auth.dto.RegisterRequest;
import ma.inpt.cloud.auth.service.AuthService;
import ma.inpt.cloud.user.User;
import ma.inpt.cloud.user.UserRepository;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

/**
 * REST controller for authentication endpoints.
 *
 * <p>All endpoints are rooted at {@code /api/auth}.
 *
 * <table border="1">
 *   <thead>
 *     <tr><th>Method</th><th>Path</th><th>Description</th></tr>
 *   </thead>
 *   <tbody>
 *     <tr><td>POST</td><td>/register</td><td>Create a new user account</td></tr>
 *     <tr><td>POST</td><td>/login</td><td>Authenticate and create a session</td></tr>
 *     <tr><td>POST</td><td>/logout</td><td>Invalidate the current session</td></tr>
 *     <tr><td>GET</td><td>/me</td><td>Return the current authenticated user's profile</td></tr>
 *   </tbody>
 * </table>
 */
@Slf4j
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;
    private final UserRepository userRepository;

    // ── POST /register ────────────────────────────────────────────────────

    /**
     * Registers a new user account.
     *
     * <p>HTTP status mapping for errors:
     * <ul>
     *   <li>{@code 409 Conflict}     – email address is already registered</li>
     *   <li>{@code 400 Bad Request}  – password is too similar to the email</li>
     *   <li>{@code 422 Unprocessable Entity} – Bean Validation failure (handled globally)</li>
     * </ul>
     *
     * @param req the validated registration payload (email + password)
     * @return {@code 201 Created} with the new account's email on success
     */
    @PostMapping("/register")
    public ResponseEntity<ApiResponse<String>> register(@Valid @RequestBody RegisterRequest req) {

        try {
            String email = authService.register(req);
            return ResponseEntity
                    .status(HttpStatus.CREATED)
                    .body(ApiResponse.ok("Account created", email));

        } catch (RuntimeException ex) {
            return switch (ex.getMessage()) {
                case "Email already in use" ->
                    ResponseEntity.status(HttpStatus.CONFLICT)
                                  .body(ApiResponse.error("An account with this email address already exists."));

                case "Password too similar to email" ->
                    ResponseEntity.status(HttpStatus.BAD_REQUEST)
                                  .body(ApiResponse.error("Password must not contain your email address."));

                default ->
                    ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                                  .body(ApiResponse.error("Registration failed. Please try again later."));
            };
        }
    }

    // ── POST /login ───────────────────────────────────────────────────────

    /**
     * Authenticates a user with email and password.
     *
     * <p>HTTP status mapping for errors:
     * <ul>
     *   <li>{@code 429 Too Many Requests} – rate limit exceeded</li>
     *   <li>{@code 403 Forbidden}          – account exists but is not active</li>
     *   <li>{@code 401 Unauthorized}       – any other authentication failure</li>
     * </ul>
     *
     * @param req        the validated login credentials
     * @param httpRequest the incoming HTTP request (used to extract the client IP)
     * @param session    the current (or newly created) HTTP session
     * @return {@code 200 OK} with the authenticated user's email on success
     */
    @PostMapping("/login")
    public ResponseEntity<ApiResponse<Map<String, String>>> login(
            @Valid @RequestBody LoginRequest req,
            HttpServletRequest httpRequest,
            HttpSession session) {

        String clientIp = httpRequest.getRemoteAddr();

        try {
            String email = authService.login(req, clientIp, session);
            Map<String, String> data = Map.of("email", email);
            return ResponseEntity.ok(ApiResponse.ok("Login successful", data));

        } catch (RuntimeException ex) {
            return switch (ex.getMessage()) {
                case "Too many requests" ->
                    ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
                                  .body(ApiResponse.error("Too many login attempts. Please try again later."));

                case "Account not active" ->
                    ResponseEntity.status(HttpStatus.FORBIDDEN)
                                  .body(ApiResponse.error("Your account is not active. Please verify your email or contact support."));

                // "Invalid credentials" and any unexpected message → 401
                default ->
                    ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                                  .body(ApiResponse.error("Invalid credentials"));
            };
        }
    }

    // ── POST /logout ──────────────────────────────────────────────────────

    /**
     * Logs the current user out by invalidating their session.
     *
     * @param session the session to invalidate
     * @return {@code 200 OK} with a confirmation message
     */
    @PostMapping("/logout")
    public ResponseEntity<ApiResponse<Void>> logout(HttpSession session) {
        authService.logout(session);
        return ResponseEntity.ok(ApiResponse.ok("Logged out successfully", null));
    }

    // ── GET /me ───────────────────────────────────────────────────────────

    /**
     * Returns the authenticated user's profile information.
     *
     * <p>Reads the {@code USER_ID} attribute from the session.  If absent the
     * caller is not logged in and a {@code 401} is returned.
     *
     * @param session the current HTTP session
     * @return {@code 200 OK} with the user's email and account status,
     *         or {@code 401 Unauthorized} if not authenticated,
     *         or {@code 404 Not Found} if the session references a deleted user
     */
    @GetMapping("/me")
    public ResponseEntity<ApiResponse<Map<String, String>>> me(HttpSession session) {

        // ── 1. Check session ──────────────────────────────────────────────
        String rawUserId = (String) session.getAttribute(AuthService.SESSION_USER_ID_KEY);
        if (rawUserId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                                 .body(ApiResponse.error("Not authenticated"));
        }

        // ── 2. Resolve user from DB ───────────────────────────────────────
        UUID userId;
        try {
            userId = UUID.fromString(rawUserId);
        } catch (IllegalArgumentException e) {
            // Should never happen unless the session was tampered with.
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                                 .body(ApiResponse.error("Invalid session"));
        }

        return userRepository.findById(userId)
            .map(user -> {
                Map<String, String> data = Map.of(
                    "email",  user.getEmail(),
                    "status", user.getStatus().name()
                );
                return ResponseEntity.ok(ApiResponse.ok("Authenticated", data));
            })
            .orElseGet(() ->
                ResponseEntity.status(HttpStatus.NOT_FOUND)
                              .<ApiResponse<Map<String, String>>>body(
                                  ApiResponse.error("User not found"))
            );
    }
}
