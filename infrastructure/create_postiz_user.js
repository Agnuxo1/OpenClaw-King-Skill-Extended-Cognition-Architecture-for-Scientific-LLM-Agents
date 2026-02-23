
const { PrismaClient } = require('@prisma/client');
const bcrypt = require('bcrypt');
const crypto = require('crypto');

const prisma = new PrismaClient();

async function main() {
  const email = '1.5bit@zohomail.eu';
  const rawPassword = '@@@AAAaaabbb37003700';
  
  console.log(`Checking user: ${email}`);

  // Check if user exists to avoid duplicates
  let user = await prisma.user.findFirst({
    where: { email }
  });

  if (user) {
    console.log('User already exists. Finding organization...');
    // Find auth
    const userOrg = await prisma.userOrganization.findFirst({
        where: { userId: user.id }
    });
    
    if (userOrg) {
        const org = await prisma.organization.findUnique({
            where: { id: userOrg.organizationId }
        });
        console.log('Existing API Key:', org.apiKey);
    } else {
        console.log('User has no organization. Creating one...');
        const apiKey = crypto.randomUUID();
        const org = await prisma.organization.create({
            data: {
                name: 'OpenCLAW Org',
                apiKey: apiKey
            }
        });
        await prisma.userOrganization.create({
            data: {
                userId: user.id,
                organizationId: org.id,
                role: 'ADMIN'
            }
        });
        console.log('New API Key:', apiKey);
    }
    
    return;
  }

  console.log('Creating new user...');
  const hashedPassword = await bcrypt.hash(rawPassword, 10);
  const apiKey = crypto.randomUUID();

  // Transaction to create User, Org, and Link
  await prisma.$transaction(async (tx) => {
    // 1. Create Organization
    const org = await tx.organization.create({
      data: {
        name: 'OpenCLAW Administration',
        apiKey: apiKey
      }
    });
    console.log(`Organization created: ${org.id}`);

    // 2. Create User
    const newUser = await tx.user.create({
      data: {
        email: email,
        password: hashedPassword,
        providerName: 'LOCAL',
        timezone: 0 // UTC offset in minutes (0 = UTC)
      }
    });
    console.log(`User created: ${newUser.id}`);

    // 3. Link User and Organization
    await tx.userOrganization.create({
      data: {
        userId: newUser.id,
        organizationId: org.id,
        role: 'ADMIN'
      }
    });
  });

  console.log('--- SUCCESS ---');
  console.log('User created:', email);
  console.log('Password:', rawPassword);
  console.log('API Key:', apiKey);
}

main()
  .catch((e) => {
    console.error('ERROR:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
