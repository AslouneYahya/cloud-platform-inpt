package ma.inpt.cloud;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Entry point for the Cloud Platform Authentication Service.
 *
 * <p>This service handles user authentication, session management,
 * and rate-limiting for the cloud platform.
 */
@SpringBootApplication
public class CloudPlatformApplication {

    public static void main(String[] args) {
        SpringApplication.run(CloudPlatformApplication.class, args);
    }
}
