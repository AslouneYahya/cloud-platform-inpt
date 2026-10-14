package ma.inpt.cloud.auth.service;

import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;

/**
 * In-process rate limiter for login attempts.
 *
 * <p>Uses the <em>token-bucket</em> algorithm (via Bucket4j) to limit how many
 * login requests a given (IP, email) pair can make in a rolling time window.
 *
 * <h3>Limits</h3>
 * <ul>
 *   <li>5 tokens per bucket.</li>
 *   <li>5 tokens refilled every 60 seconds (greedy refill).</li>
 *   <li>Key = {@code "<ip>:<email>"} — scoped to the combination, not just the IP.</li>
 * </ul>
 *
 * <h3>Notes</h3>
 * <p>This implementation stores buckets in a {@link ConcurrentHashMap} held in
 * the JVM heap.  It is stateless across restarts and across multiple instances.
 * For a distributed deployment, replace the map with a Redis-backed Bucket4j
 * proxy (Bucket4j-Redis or Bucket4j-Caffeine + Redis sync).
 */
@Service
public class RateLimitService {

    /** Maximum number of tokens in each bucket (= max burst). */
    private static final int CAPACITY = 5;

    /** How many tokens are added per refill interval. */
    private static final int REFILL_AMOUNT = 5;

    /** Refill interval: one minute. */
    private static final Duration REFILL_PERIOD = Duration.ofMinutes(1);

    /**
     * Per-key bucket store.
     * Key format: {@code "<clientIp>:<normalizedEmail>"}.
     */
    private final ConcurrentHashMap<String, Bucket> buckets = new ConcurrentHashMap<>();

    // ── Public API ────────────────────────────────────────────────────────

    /**
     * Checks whether the (ip, email) pair is allowed to proceed with a login
     * attempt, and if so, consumes one token.
     *
     * @param ip    the client's remote IP address
     * @param email the email address being used in the login attempt (normalised to lower-case by the caller)
     * @return {@code true} if the request is within rate limits; {@code false} if the bucket is empty
     */
    public boolean isAllowed(String ip, String email) {
        String key = ip + ":" + email;
        Bucket bucket = buckets.computeIfAbsent(key, k -> buildBucket());
        return bucket.tryConsume(1);
    }

    // ── Internal helpers ──────────────────────────────────────────────────

    /**
     * Constructs a new Bucket4j token bucket with the configured capacity and
     * greedy refill policy.
     *
     * @return a fully configured {@link Bucket}
     */
    private Bucket buildBucket() {
        // Bucket4j 8.x fluent builder API
        // Greedy refill: tokens are added continuously over the period
        Bandwidth limit = Bandwidth.builder()
                .capacity(CAPACITY)
                .refillGreedy(REFILL_AMOUNT, REFILL_PERIOD)
                .build();
        return Bucket.builder()
                     .addLimit(limit)
                     .build();
    }
}
