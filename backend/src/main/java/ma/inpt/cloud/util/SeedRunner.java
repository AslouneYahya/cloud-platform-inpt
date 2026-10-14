package ma.inpt.cloud.util;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.inpt.cloud.user.AccountStatus;
import ma.inpt.cloud.user.User;
import ma.inpt.cloud.user.UserRepository;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/**
 * SeedRunner — populates the database with demo users when the {@code seed}
 * Spring profile is active.
 *
 * <p>Activation:
 * <pre>
 *   docker compose run --rm -e SPRING_PROFILES_ACTIVE=seed backend
 * </pre>
 *
 * <p>The runner is idempotent: if any user records already exist it logs a
 * message and exits without modifying the database.
 *
 * <p>Passwords are encoded at runtime using the application's configured
 * {@link PasswordEncoder} (Argon2id, parameters: m=65536, t=3, p=1, saltLen=16,
 * hashLen=32) so that valid hashes are always produced without hard-coding them.
 */
@Slf4j
@Component
@Profile("seed")
@RequiredArgsConstructor
public class SeedRunner implements CommandLineRunner {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Override
    public void run(String... args) {

        // ── Guard: skip if data already present ───────────────────────────────
        if (userRepository.count() > 0) {
            log.info("Seed data already present, skipping.");
            return;
        }

        log.info("No existing users found — seeding demo data …");

        // ── 1. Admin user ─────────────────────────────────────────────────────
        User admin = User.builder()
                .email("admin@inpt.ma")
                .passwordHash(passwordEncoder.encode("Admin1234!"))
                .status(AccountStatus.ACTIVE)
                .failedLoginAttempts(0)
                .build();

        userRepository.save(admin);
        log.info("Seeded user: {}", admin.getEmail());

        // ── 2. Demo user ──────────────────────────────────────────────────────
        User demo = User.builder()
                .email("demo@inpt.ma")
                .passwordHash(passwordEncoder.encode("Demo1234!"))
                .status(AccountStatus.ACTIVE)
                .failedLoginAttempts(0)
                .build();

        userRepository.save(demo);
        log.info("Seeded user: {}", demo.getEmail());

        log.info("Seeding complete — {} demo user(s) created.", 2);
    }
}
