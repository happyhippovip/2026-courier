// pgvector-local-kit — Environment & Docker Config Switcher
// Zero external dependencies.

class EnvSwitcher {
  static generateDockerCompose({
    containerName = 'pgvector_local',
    port = 5432,
    dbUser = 'postgres',
    dbPass = 'postgres',
    dbName = 'local_agent_db'
  } = {}) {
    return `version: '3.8'

services:
  ${containerName}:
    image: pgvector/pgvector:pg16
    container_name: ${containerName}
    environment:
      POSTGRES_USER: ${dbUser}
      POSTGRES_PASSWORD: ${dbPass}
      POSTGRES_DB: ${dbName}
    ports:
      - "${port}:5432"
    volumes:
      - pgvector_data:/var/lib/postgresql/data
    command: >
      postgres
      -c shared_buffers=512MB
      -c work_mem=64MB
      -c maintenance_work_mem=256MB
      -c max_connections=50
    restart: unless-stopped

volumes:
  pgvector_data:
`;
  }

  static switchConnection({ envContent, targetMode = 'local', localPort = 5432, dbName = 'local_agent_db' } = {}) {
    if (typeof envContent !== 'string') {
      throw new Error('[ENV_SWITCHER_ERROR] envContent must be a string');
    }

    const lines = envContent.split('\n');
    const localUrl = `postgresql://postgres:postgres@localhost:${localPort}/${dbName}`;
    let foundDbUrl = false;

    const modified = lines.map(line => {
      if (line.startsWith('DATABASE_URL=') || line.startsWith('POSTGRES_URL=')) {
        foundDbUrl = true;
        if (targetMode === 'local') {
          return `DATABASE_URL="${localUrl}" # SWAPPED TO LOCAL BY pgvector-local-kit`;
        }
      }
      if (line.startsWith('NEXT_PUBLIC_SUPABASE_URL=') && targetMode === 'local') {
        return `# ${line} (Disabled for local offline agent execution)`;
      }
      return line;
    });

    if (!foundDbUrl && targetMode === 'local') {
      modified.push(`DATABASE_URL="${localUrl}"`);
    }

    return modified.join('\n');
  }
}

module.exports = { EnvSwitcher };
