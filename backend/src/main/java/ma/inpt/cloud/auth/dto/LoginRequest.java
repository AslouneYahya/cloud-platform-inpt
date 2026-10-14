package ma.inpt.cloud.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

/**
 * Request payload for the {@code POST /api/auth/login} endpoint.
 *
 * <p>Both fields are mandatory and validated by the Jakarta Bean Validation
 * framework before the controller method is invoked.
 *
 * @param email    the user's email address (must be a well-formed email)
 * @param password the raw password supplied by the user (never logged or stored)
 */
public record LoginRequest(

    /** A well-formed, non-blank email address. */
    @Email(message = "Must be a valid email address")
    @NotBlank(message = "Email must not be blank")
    String email,

    /** The user's plaintext password (validated against the stored Argon2id hash). */
    @NotBlank(message = "Password must not be blank")
    String password
) {}
