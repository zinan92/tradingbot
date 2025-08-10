#!/usr/bin/env node

const pact = require('@pact-foundation/pact-node');
const path = require('path');
const { version } = require('../package.json');

const PACT_BROKER_URL = process.env.PACT_BROKER_URL || 'http://localhost:9292';
const PACT_BROKER_USERNAME = process.env.PACT_BROKER_USERNAME || 'pact';
const PACT_BROKER_PASSWORD = process.env.PACT_BROKER_PASSWORD || 'pact';

const opts = {
  pactFilesOrDirs: [path.resolve(process.cwd(), 'pacts')],
  pactBroker: PACT_BROKER_URL,
  pactBrokerUsername: PACT_BROKER_USERNAME,
  pactBrokerPassword: PACT_BROKER_PASSWORD,
  consumerVersion: version,
  tags: [process.env.GIT_BRANCH || 'main']
};

console.log('Publishing pacts to broker...');
console.log(`Broker URL: ${PACT_BROKER_URL}`);
console.log(`Consumer Version: ${version}`);
console.log(`Tags: ${opts.tags.join(', ')}`);

pact.publishPacts(opts)
  .then(() => {
    console.log('Pacts successfully published!');
    process.exit(0);
  })
  .catch((e) => {
    console.error('Failed to publish pacts:', e);
    process.exit(1);
  });