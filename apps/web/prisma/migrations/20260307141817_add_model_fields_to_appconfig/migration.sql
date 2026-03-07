-- AlterTable
ALTER TABLE "AppConfig" ADD COLUMN     "modelCreationLm" TEXT NOT NULL DEFAULT 'gpt-5',
ADD COLUMN     "modelCreationMail" TEXT NOT NULL DEFAULT 'gpt-5',
ADD COLUMN     "modelCvReader" TEXT NOT NULL DEFAULT 'Qwen2.5-VL-72B-Instruct',
ADD COLUMN     "modelEnrichissement" TEXT NOT NULL DEFAULT 'spark-1-mini',
ADD COLUMN     "modelEnrichissement2" TEXT NOT NULL DEFAULT 'sonar-pro',
ADD COLUMN     "modelKeywords" TEXT NOT NULL DEFAULT 'gpt-5',
ADD COLUMN     "modelRanking" TEXT NOT NULL DEFAULT 'gemini-2.5-flash';
