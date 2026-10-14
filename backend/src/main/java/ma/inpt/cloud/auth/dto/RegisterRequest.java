package ma.inpt.cloud.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * Payload for the {@code POST /api/auth/register} endpoint.
 *
 * <p>Validation is enforced via Bean Validation annotations and applied by
 * Spring MVC when the parameter is annotated with {@code @Valid}.
 *
 * @param email    the user's email address (must be well-formed and non-blank)
 * @param password the user's raw password (8–128 characters, non-blank)
 */
public record RegisterRequest(

        @Email(message = "Email must be a valid email address")
        @NotBlank(message = "Email must not be blank")
        String email,

        @NotBlank(message = "Password must not be blank")
        @Size(min = 8, max = 128, message = "Password must be between 8 and 128 characters")
        String password
) {}
