package ma.inpt.cloud.user;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

/**
 * Spring Data JPA repository for {@link User} entities.
 *
 * <p>The {@code findByEmailIgnoreCase} query performs a case-insensitive
 * look-up so that "User@Example.com" and "user@example.com" resolve to the
 * same account.  Emails should still be normalised to lower-case before being
 * stored, but this guard prevents duplicate-account edge cases.
 */
@Repository
public interface UserRepository extends JpaRepository<User, UUID> {

    /**
     * Finds a user whose email matches the given value, ignoring case.
     *
     * @param email the email address to look up (any casing)
     * @return an {@link Optional} containing the matching user, or empty if none found
     */
    Optional<User> findByEmailIgnoreCase(String email);
}
