-- AlterTable
ALTER TABLE "Campaign" ADD COLUMN     "sectors" TEXT[] DEFAULT ARRAY[]::TEXT[];
