package ma.inpt.cloud.auth.dto;

/**
 * Generic API envelope used for all controller responses.
 *
 * <p>Every response — success or error — is wrapped in this record so that
 * clients always receive a consistent JSON structure:
 * <pre>{@code
 * {
 *   "message": "Login successful",
 *   "data": { ... }
 * }
 * }</pre>
 *
 * <p>For error responses {@code data} will be {@code null}.
 *
 * @param <T>     the type of the response payload
 * @param message a human-readable status message
 * @param data    the response payload, or {@code null} for error responses
 */
public record ApiResponse<T>(String message, T data) {

    // ── Static factory methods ────────────────────────────────────────────

    /**
     * Creates a successful response with a payload.
     *
     * @param message a description of the successful operation
     * @param data    the response payload
     * @param <T>     the type of the payload
     * @return a populated {@link ApiResponse}
     */
    public static <T> ApiResponse<T> ok(String message, T data) {
        return new ApiResponse<>(message, data);
    }

    /**
     * Creates an error response with no payload.
     *
     * @param message a description of the error
     * @param <T>     unused type parameter (kept generic for assignment compatibility)
     * @return an {@link ApiResponse} with {@code null} data
     */
    public static <T> ApiResponse<T> error(String message) {
        return new ApiResponse<>(message, null);
    }
}
