// Sentinex — Neo4j initialization.
// Indexes + constraints for Graphiti's node/edge schema with tenant isolation
// via the `group_id` property (Community-edition-friendly setup).

CREATE CONSTRAINT entity_uuid_unique IF NOT EXISTS
FOR (n:Entity) REQUIRE n.uuid IS UNIQUE;

CREATE CONSTRAINT episode_uuid_unique IF NOT EXISTS
FOR (n:Episodic) REQUIRE n.uuid IS UNIQUE;

CREATE CONSTRAINT community_uuid_unique IF NOT EXISTS
FOR (n:Community) REQUIRE n.uuid IS UNIQUE;

CREATE INDEX entity_group_id IF NOT EXISTS FOR (n:Entity) ON (n.group_id);
CREATE INDEX episode_group_id IF NOT EXISTS FOR (n:Episodic) ON (n.group_id);
CREATE INDEX entity_name IF NOT EXISTS FOR (n:Entity) ON (n.name);
CREATE INDEX episode_valid_at IF NOT EXISTS FOR (n:Episodic) ON (n.valid_at);
