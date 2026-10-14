package ma.inpt.cloud.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.argon2.Argon2PasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

/**
 * Spring Security configuration for the authentication service.
 *
 * <h3>Key decisions</h3>
 * <ul>
 *   <li><strong>CSRF disabled</strong> – The API uses session cookies with
 *       {@code SameSite=Strict} (configured at the servlet container level)
 *       instead of a CSRF token.  This is safe for SPA/mobile clients that
 *       always send requests from an allowed origin.</li>
 *   <li><strong>Argon2id</strong> – The OWASP-recommended password hashing
 *       algorithm.  Parameters match the OWASP "interactive login" profile:
 *       16-byte salt, 32-byte output, parallelism 1, 64 MiB memory, 3 iterations.</li>
 *   <li><strong>Security headers</strong> – HSTS (2 years + subdomains),
 *       X-Frame-Options DENY, X-Content-Type-Options nosniff, and a basic
 *       Referrer-Policy are set on every response.</li>
 * </ul>
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    // ── Allowed origins ───────────────────────────────────────────────────

    private static final String LOCAL_ORIGIN_HTTPS = "https://localhost";
    private static final String LOCAL_ORIGIN_HTTP  = "http://localhost";
    private static final String LOCAL_ORIGIN_VITE  = "http://localhost:5173";
    private static final String PRODUCTION_ORIGIN  = "https://yourstartup.com";

    // ── Beans ─────────────────────────────────────────────────────────────

    /**
     * Argon2id password encoder configured to the OWASP interactive-login profile.
     *
     * <ul>
     *   <li>Salt length: 16 bytes</li>
     *   <li>Hash length: 32 bytes</li>
     *   <li>Parallelism: 1</li>
     *   <li>Memory:      65 536 KiB (64 MiB)</li>
     *   <li>Iterations:  3</li>
     * </ul>
     *
     * @return a configured {@link Argon2PasswordEncoder}
     */
    @Bean
    public PasswordEncoder passwordEncoder() {
        // Argon2PasswordEncoder(saltLength, hashLength, parallelism, memoryKiB, iterations)
        return new Argon2PasswordEncoder(16, 32, 1, 65_536, 3);
    }

    /**
     * Main security filter chain.
     *
     * @param http the {@link HttpSecurity} builder provided by Spring Security
     * @return the configured {@link SecurityFilterChain}
     * @throws Exception if configuration fails
     */
    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {

        http
            // ── CSRF ─────────────────────────────────────────────────────
            // Disabled in favour of SameSite=Strict cookie attribute.
            .csrf(csrf -> csrf.disable())

            // ── CORS ─────────────────────────────────────────────────────
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))

            // ── Authorisation rules ───────────────────────────────────────
            .authorizeHttpRequests(auth -> auth
                // All auth and VM endpoints self-manage session or are public
                .requestMatchers("/api/auth/**").permitAll()
                .requestMatchers("/api/vms/**").permitAll()
                .requestMatchers("/actuator/health").permitAll()
                // Everything else requires a valid session
                .anyRequest().authenticated()
            )

            // ── Session management ────────────────────────────────────────
            // IF_REQUIRED: Spring creates a session only when one is needed
            // (e.g. after successful login).  This avoids creating sessions
            // for unauthenticated requests to public endpoints.
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED)
                // Protect against session-fixation attacks:
                // invalidate the old session and create a new one on auth.
                .sessionFixation(fixation -> fixation.migrateSession())
            )

            // ── Disable unused auth mechanisms ────────────────────────────
            .formLogin(form -> form.disable())
            .httpBasic(basic -> basic.disable())

            // ── Security response headers ─────────────────────────────────
            .headers(headers -> headers
                // Prevent clickjacking
                .frameOptions(frame -> frame.deny())
                // Prevent MIME-type sniffing
                .contentTypeOptions(content -> {}) // enabled by default; keep
                // HSTS: 2 years, include subdomains (no preload — add manually if needed)
                .httpStrictTransportSecurity(hsts -> hsts
                    .maxAgeInSeconds(63_072_000)   // 2 years
                    .includeSubDomains(true)
                )
                // Basic referrer policy
                .referrerPolicy(referrer -> referrer
                    .policy(ReferrerPolicyHeaderWriter.ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN)
                )
            );

        return http.build();
    }

    /**
     * CORS policy applied to all requests through the security filter chain.
     *
     * <p>Credentials (cookies) are allowed so that the session cookie is
     * included in cross-origin requests from the SPA.
     *
     * @return the configured {@link CorsConfigurationSource}
     */
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();

        // Allowed origins (explicit list required when allowCredentials = true)
        config.setAllowedOrigins(List.of(
            LOCAL_ORIGIN_HTTPS,
            LOCAL_ORIGIN_HTTP,
            LOCAL_ORIGIN_VITE,
            PRODUCTION_ORIGIN
        ));

        // Allowed HTTP methods
        config.setAllowedMethods(List.of(
            HttpMethod.GET.name(),
            HttpMethod.POST.name(),
            HttpMethod.DELETE.name(),
            HttpMethod.OPTIONS.name()
        ));

        // Allow all request headers (Authorization, Content-Type, X-Requested-With, etc.)
        config.setAllowedHeaders(List.of("*"));

        // Allow the browser to send and receive cookies (session cookie)
        config.setAllowCredentials(true);

        // Cache preflight responses for 1 hour
        config.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}
