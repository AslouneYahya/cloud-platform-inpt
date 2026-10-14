package ma.inpt.cloud.vm;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface VmRepository extends JpaRepository<Vm, UUID> {

    List<Vm> findByOwnerIdOrderByCreatedAtDesc(UUID ownerId);

    Optional<Vm> findByIdAndOwnerId(UUID id, UUID ownerId);

    long countByOwnerIdAndStatusNot(UUID ownerId, VmStatus status);
}
