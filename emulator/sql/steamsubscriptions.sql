-- phpMyAdmin SQL Dump
-- version 4.8.5
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Jul 02, 2023 at 03:44 AM
-- Server version: 10.1.38-MariaDB
-- PHP Version: 5.6.40

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET AUTOCOMMIT = 0;
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `stmserver`
--

-- --------------------------------------------------------

--
-- Table structure for table `steamsubscriptions`
--

CREATE TABLE `steamsubscriptions` (
  `SubscriptionID` int(11) NOT NULL,
  `Name` varchar(256) NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

--
-- Dumping data for table `steamsubscriptions`
--

INSERT INTO `steamsubscriptions` (`SubscriptionID`, `Name`) VALUES
(0, 'Steam'),
(1, 'Half-Life Platinum Pack'),
(2, 'Day of Defeat'),
(3, 'Condition Zero'),
(4, 'Cyber Cafe'),
(5, 'ATI Bundle'),
(6, 'Condition Zero'),
(7, 'Condition Zero'),
(8, 'Valve Premier Pack'),
(9, 'Half-Life 2 Bronze'),
(10, 'Half-Life 2 Silver'),
(11, 'Half-Life 2 Retail Standard'),
(12, 'Half-Life 2 Retail Collectors'),
(13, 'Half-Life 2 Gold'),
(14, 'HL2 Complimentary Edition'),
(15, 'AMD Bundle'),
(16, 'DoD:S Beta Test'),
(17, 'Valve Test App 120 Sub'),
(18, 'Valve Test App 1000 Sub'),
(19, 'Half-Life 2 Game of the Year'),
(20, 'Counter-Strike 1 Anthology'),
(21, 'Half Life 1 Anthology'),
(22, 'Counter-Strike Source'),
(23, 'Half-Life 2 Platinum'),
(24, 'Half-Life 1 Classic'),
(25, 'Day of Defeat: Source'),
(26, 'Online Multiplayer'),
(27, 'DoD_Review'),
(29, 'Team Fortress Classic'),
(30, 'Day of Defeat'),
(31, 'Deathmatch Classic'),
(32, 'Opposing Force'),
(33, 'Ricochet'),
(34, 'Half-Life 1'),
(35, 'Half-Life: Blue Shift'),
(36, 'Half-Life 2'),
(37, 'Counter-Strike: Source'),
(38, 'Half-Life 1: Source'),
(39, 'Half-Life 2: Deathmatch'),
(40, 'Half-Life 1 Anthology'),
(41, 'Counter-Strike 1 Anthology'),
(42, 'Source Multiplayer Pack'),
(43, 'Source Premier Pack'),
(44, 'Valve Complete Pack'),
(45, 'Rag Doll Kung Fu'),
(46, 'Rag Doll Kung Fu Complementary'),
(47, 'Day of Defeat: Source Promo'),
(48, 'Valve Test App 1309 Sub'),
(49, 'School Lab'),
(50, 'Gift Pack'),
(51, 'Valve Test App 1100'),
(52, 'Rag Doll Kung Fu Test'),
(53, 'Red Orchestra Beta'),
(54, 'Darwinia'),
(55, 'Darwinia Complementary'),
(56, 'Day of Defeat Source'),
(57, 'Space Empires IV Deluxe'),
(58, 'SCS - Dangerous Waters'),
(59, 'Space Empires IV Deluxe Complementary'),
(60, 'SCS - Dangerous Waters Complementary'),
(61, 'Steam Master'),
(62, 'Press Master'),
(63, 'Red Orchestra'),
(64, 'Red Orchestra Retail'),
(65, 'Red Orchestra Complementary'),
(66, 'GNA/WEG Tournament Promotion'),
(67, 'VTT'),
(68, 'Valve Complete Pack Complementary'),
(69, 'SiN Episodes Emergence'),
(70, 'Sin Episode 1'),
(71, 'Rag Doll Kung Fu'),
(72, 'Earth 2160'),
(73, 'Earth 2160 Complementary'),
(74, 'Valve Test Sub 74'),
(75, 'Sin Episode 1 DE'),
(76, 'Condition Zero and Counter-Strike'),
(77, 'Half-Life 2: Episode One'),
(78, 'SiN Episodes Emergence DE'),
(79, 'Half-Life 2: Episode One'),
(80, 'Source Premier Pack'),
(81, 'Valve Complete Pack'),
(82, 'Half-Life 2: Lost Coast and Deathmatch'),
(83, 'SiN Episodes Emergence OEM'),
(84, 'Half-Life 2: Episode One OEM'),
(85, 'Shadowgrounds'),
(86, 'Shadowgrounds Complimentary'),
(87, 'The Ship Beta'),
(88, 'Sci-Fi Strategy Pack'),
(89, 'SiN Episodes Emergence Germany'),
(90, 'The Ship'),
(91, 'The Ship Complimentary'),
(92, 'Day of Defeat Source'),
(93, 'SiN Episodes Emergence'),
(94, 'Jagged Alliance 2'),
(95, 'Disciples II Gold'),
(96, 'Jagged Alliance 2 / Disciples II Gold Combo'),
(97, 'Jagged Alliance 2 Complimentary'),
(98, 'Disciples II Gold Complimentary'),
(99, 'X2/X3 Complimentary'),
(100, 'X2: The Threat'),
(101, 'X3: Reunion'),
(102, 'X2: The Threat / X3: Reunion'),
(103, 'Birth of America'),
(104, 'Iron Warriors'),
(105, 'Birth of America Complimentary'),
(106, 'Iron Warriors Complimentary'),
(107, 'Sci-Fi Game Pack'),
(108, 'Half-Life 2 Classic'),
(109, 'The Ship Retail'),
(110, 'Uplink Beta'),
(111, 'Sniper Elite Beta'),
(112, 'Uplink'),
(113, 'Darwinia / Uplink'),
(114, 'GTI Racing'),
(115, 'Xpand Rally'),
(116, 'GTI/Xpand Pack'),
(117, 'GTI/Xpand Pack with MOMO Racing Wheel'),
(118, 'GTI Racing Retail'),
(119, 'GTI/Xpand Pack Retail'),
(120, 'PopCap Complimentary'),
(121, 'Bejeweled 2 Deluxe'),
(122, 'Bejeweled Deluxe'),
(123, 'Zuma Deluxe'),
(124, 'Feeding Frenzy 2 Deluxe'),
(125, 'Bookworm Deluxe'),
(126, 'Chuzzle Deluxe'),
(127, 'Insaniquarium Deluxe'),
(128, 'Dynomite Deluxe'),
(129, 'Iggle Pop Deluxe'),
(130, 'Pizza Frenzy'),
(131, 'Typer Shark Deluxe'),
(132, 'AstroPop Deluxe'),
(133, 'Heavy Weapon Deluxe'),
(134, 'Rocket Mania Deluxe'),
(135, 'Hammer Heads Deluxe'),
(136, 'Big Money Deluxe'),
(137, 'Talismania Deluxe'),
(138, 'Puzzle Pack'),
(139, 'Action Pack'),
(140, 'Thinking Pack'),
(141, 'Puzzle + Action Pack'),
(142, 'Thinking + Action Pack'),
(143, 'Puzzle + Thinking Pack'),
(144, 'The Complete PopCap Collection'),
(145, 'Dark Messiah Steam Beta'),
(146, 'Majesco Complimentary'),
(147, 'Strategy First Complimentary'),
(148, 'Counter-Strike: Source'),
(149, 'Counter-Strike'),
(150, 'Half-Life 2: Deathmatch / Half-Life 2: Lost Coast'),
(151, 'Half-Life 2 Holiday Pack 2006'),
(152, 'Half-Life 2 Holiday 2006'),
(153, 'BloodRayne'),
(154, 'BloodRayne 2'),
(155, 'Advent Rising'),
(156, 'Defcon'),
(158, 'ValveTestSub 158 Complimentary'),
(159, 'Defcon Demo Beta'),
(160, 'Defcon Beta'),
(161, 'Space Empires V Complimentary'),
(162, 'Psychonauts Beta'),
(163, 'ValveTestSub163 Complimentary'),
(164, 'Dark Messiah'),
(165, 'Sci-Fi Game Pack');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `steamsubscriptions`
--
ALTER TABLE `steamsubscriptions`
  ADD PRIMARY KEY (`SubscriptionID`),
  ADD UNIQUE KEY `SubscriptionID_UNIQUE` (`SubscriptionID`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
