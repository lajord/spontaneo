-- CreateTable
CREATE TABLE "AgentCandidate" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "campaignId" TEXT,
    "name" TEXT NOT NULL,
    "domain" TEXT,
    "websiteUrl" TEXT,
    "city" TEXT,
    "description" TEXT,
    "source" TEXT,
    "secteur" TEXT,
    "jobTitle" TEXT,
    "location" TEXT,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "AgentCandidate_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "AgentCandidate_userId_status_idx" ON "AgentCandidate"("userId", "status");

-- CreateIndex
CREATE UNIQUE INDEX "AgentCandidate_userId_domain_key" ON "AgentCandidate"("userId", "domain");

-- AddForeignKey
ALTER TABLE "AgentCandidate" ADD CONSTRAINT "AgentCandidate_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
