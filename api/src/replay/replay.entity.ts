import { Column, CreateDateColumn, Entity, PrimaryGeneratedColumn, UpdateDateColumn } from 'typeorm';

@Entity({ name: 'replays' })
export class ReplayEntity {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ name: 'env_id', unique: true })
  envId!: string;

  @Column({ name: 'seed', nullable: true })
  seed?: string;

  @Column({ name: 'ruleset_version', nullable: true })
  rulesetVersion?: string;

  @Column({ type: 'simple-json', name: 'actions', nullable: false, default: '[]' })
  actions!: Array<Record<string, unknown> | null>;

  @Column({ type: 'simple-json', name: 'states', nullable: false, default: '[]' })
  states!: Record<string, unknown>[];

  @Column({ type: 'simple-json', name: 'state_hashes', nullable: false, default: '[]' })
  stateHashes!: string[];

  @CreateDateColumn({ name: 'created_at' })
  createdAt!: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt!: Date;
}
