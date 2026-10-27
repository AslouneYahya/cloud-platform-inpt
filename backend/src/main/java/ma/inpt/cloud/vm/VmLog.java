package ma.inpt.cloud.vm;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * JPA entity capturing AWS CloudWatch-style live provisioning and lifecycle logs for a VM.
 */
@Entity
@Table(name = "vm_logs", indexes = {
    @Index(name = "idx_vm_logs_vm_id", columnList = "vm_id"),
    @Index(name = "idx_vm_logs_timestamp", columnList = "timestamp")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class VmLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "vm_id", nullable = false)
    private UUID vmId;

    @Column(name = "stage", length = 50)
    private String stage;

    @Column(name = "level", length = 20)
    private String level; // INFO, SUCCESS, WARN, ERROR

    @Column(name = "message", length = 1000, nullable = false)
    private String message;

    @Column(name = "timestamp", nullable = false, updatable = false)
    private LocalDateTime timestamp;

    @PrePersist
    public void prePersist() {
        if (this.timestamp == null) {
            this.timestamp = LocalDateTime.now();
        }
    }
}
