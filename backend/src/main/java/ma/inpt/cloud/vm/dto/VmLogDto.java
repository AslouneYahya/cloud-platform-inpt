package ma.inpt.cloud.vm.dto;

import ma.inpt.cloud.vm.VmLog;
import java.time.LocalDateTime;

public record VmLogDto(
    Long id,
    String stage,
    String level,
    String message,
    LocalDateTime timestamp
) {
    public static VmLogDto fromEntity(VmLog log) {
        return new VmLogDto(
            log.getId(),
            log.getStage(),
            log.getLevel(),
            log.getMessage(),
            log.getTimestamp()
        );
    }
}
